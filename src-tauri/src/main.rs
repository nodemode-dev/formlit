#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine_start;
mod reveal;
#[cfg(windows)]
mod win_job;

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons};
use tauri_plugin_updater::UpdaterExt;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[cfg(windows)]
const ENGINE_PROGRAM: &str = "formlit-engine.exe";

#[cfg(not(windows))]
const ENGINE_PROGRAM: &str = "formlit-engine";

struct Backend(Mutex<Option<Child>>);

const ENGINE_PORT: &str = "8390";
const FALLBACK_LOGICAL: (f64, f64) = (1440.0, 900.0);
const MIN_LOGICAL: (f64, f64) = (1080.0, 680.0);
const SCREEN_FRACTION: f64 = 0.9;

fn kill_backend(handle: &tauri::AppHandle) {
    let state = handle.state::<Backend>();
    let child = state.0.lock().ok().and_then(|mut slot| slot.take());
    if let Some(mut child) = child {
        #[cfg(windows)]
        win_job::end();
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn close_splash(handle: &tauri::AppHandle) {
    if let Some(splash) = handle.get_webview_window("splash") {
        let _ = splash.close();
    }
}

fn check_for_updates(handle: tauri::AppHandle) {
    let configured = handle
        .config()
        .plugins
        .0
        .get("updater")
        .and_then(|updater| updater.get("pubkey"))
        .and_then(|key| key.as_str())
        .map_or(false, |key| !key.is_empty());
    if !configured {
        return;
    }
    tauri::async_runtime::spawn(async move {
        let Ok(updater) = handle.updater() else { return };
        let Ok(Some(update)) = updater.check().await else { return };
        let install = handle
            .dialog()
            .message(format!("formlit {} is available. Install it and restart?", update.version))
            .title("Update available")
            .buttons(MessageDialogButtons::OkCancel)
            .blocking_show();
        if install && update.download_and_install(|_, _| {}, || {}).await.is_ok() {
            kill_backend(&handle);
            handle.restart();
        }
    });
}

fn engine_program() -> Option<std::path::PathBuf> {
    let exe = tauri::utils::platform::current_exe().ok()?;
    let program = exe.parent()?.join(ENGINE_PROGRAM);
    program.is_file().then_some(program)
}

fn forward_lines<R: std::io::Read + Send + 'static>(stream: R, tx: tauri::async_runtime::Sender<String>) {
    std::thread::spawn(move || {
        for line in BufReader::new(stream).split(b'\n') {
            let Ok(bytes) = line else { break };
            let _ = tx.blocking_send(String::from_utf8_lossy(&bytes).into_owned());
        }
    });
}

fn start_engine(program: &std::path::Path) -> std::io::Result<(Child, tauri::async_runtime::Receiver<String>)> {
    let mut command = Command::new(program);
    command
        .env("FORMLIT_PORT", ENGINE_PORT)
        .env("FORMLIT_WINDOW_KEY_STDOUT", "1")
        .env(engine_start::SHELL_ENV, std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let mut child = command.spawn()?;
    #[cfg(windows)]
    win_job::hold(&child);
    let (tx, rx) = tauri::async_runtime::channel::<String>(64);
    if let Some(stdout) = child.stdout.take() {
        forward_lines(stdout, tx.clone());
    }
    if let Some(stderr) = child.stderr.take() {
        forward_lines(stderr, tx);
    }
    Ok((child, rx))
}

async fn read_port(
    mut rx: tauri::async_runtime::Receiver<String>,
    tail: &mut engine_start::Tail,
) -> Result<(u16, Option<String>), engine_start::Failure> {
    let pattern = regex::Regex::new(r"http://127\.0\.0\.1:(\d+)").unwrap();
    let key_pattern = regex::Regex::new(r"formlit-window-key: ([A-Za-z0-9_-]{32,})").unwrap();
    let mut key: Option<String> = None;
    let mut port: Option<u16> = None;
    let mut waiting = engine_start::Wait::Address;
    let (tick, mut timer) = tauri::async_runtime::channel::<()>(1);
    std::thread::spawn(move || {
        std::thread::sleep(engine_start::Wait::Address.limit());
        let _ = tick.blocking_send(());
    });
    loop {
        let next: Result<Option<String>, ()> = std::future::poll_fn(|cx| match timer.poll_recv(cx) {
            std::task::Poll::Ready(_) => std::task::Poll::Ready(Err(())),
            std::task::Poll::Pending => rx.poll_recv(cx).map(Ok),
        })
        .await;
        let text = match next {
            Err(()) => return Err(engine_start::Failure::TimedOut(waiting)),
            Ok(None) => return Err(engine_start::Failure::Stopped(None)),
            Ok(Some(text)) => text,
        };
        tail.push(&text);
        if key.is_none() {
            key = key_pattern.captures(&text).map(|found| found[1].to_string());
        }
        if port.is_none() {
            port = pattern.captures(&text).and_then(|found| found[1].parse::<u16>().ok());
            if port.is_some() && key.is_none() {
                let (key_tick, key_timer) = tauri::async_runtime::channel::<()>(1);
                std::thread::spawn(move || {
                    std::thread::sleep(engine_start::Wait::Key.limit());
                    let _ = key_tick.blocking_send(());
                });
                timer = key_timer;
                waiting = engine_start::Wait::Key;
            }
        }
        if let (Some(found), true) = (port, key.is_some()) {
            tauri::async_runtime::spawn(async move { while rx.recv().await.is_some() {} });
            return Ok((found, key));
        }
    }
}

fn open_main(handle: &tauri::AppHandle, port: u16, key: Option<&str>) -> bool {
    let origin = format!("http://127.0.0.1:{port}");
    let Ok(url) = origin.parse::<tauri::Url>() else { return false };
    let (width, height) = handle
        .primary_monitor()
        .ok()
        .flatten()
        .map(|monitor| {
            let size = monitor.size();
            let scale = monitor.scale_factor();
            (
                (size.width as f64 / scale) * SCREEN_FRACTION,
                (size.height as f64 / scale) * SCREEN_FRACTION,
            )
        })
        .unwrap_or(FALLBACK_LOGICAL);
    let builder = WebviewWindowBuilder::new(handle, "main", WebviewUrl::External(url))
        .title("FormLit")
        .visible(reveal::BUILD_VISIBLE)
        .background_color(reveal::BACKGROUND)
        .inner_size(width, height)
        .min_inner_size(MIN_LOGICAL.0, MIN_LOGICAL.1)
        .center();
    let builder = match key {
        Some(value) => builder.initialization_script(format!(
            "if (window.location.origin === {origin:?}) {{ window.__FORMLIT_WINDOW_KEY = {value:?}; }}"
        )),
        None => builder,
    };
    match builder.build() {
        Ok(window) => {
            reveal::conceal(&window);
            true
        }
        Err(_) => false,
    }
}

fn engine_exit_code(handle: &tauri::AppHandle) -> Option<i32> {
    let state = handle.state::<Backend>();
    let mut waited = std::time::Duration::ZERO;
    while waited < engine_start::EXIT_WAIT {
        if let Ok(mut slot) = state.0.lock() {
            let seen = slot.as_mut().map(|child| child.try_wait());
            match seen {
                Some(Ok(Some(status))) => return status.code(),
                Some(Ok(None)) => {}
                _ => return None,
            };
        }
        std::thread::sleep(engine_start::EXIT_STEP);
        waited += engine_start::EXIT_STEP;
    }
    None
}

fn engine_failed(handle: &tauri::AppHandle, failure: engine_start::Failure, tail: &engine_start::Tail) {
    let failure = match failure {
        engine_start::Failure::Stopped(None) => engine_start::Failure::Stopped(engine_exit_code(handle)),
        other => other,
    };
    let text = engine_start::message(&failure, &tail.lines(), engine_start::engine_log().as_deref());
    let _ = handle
        .dialog()
        .message(text)
        .title(engine_start::APP)
        .kind(tauri_plugin_dialog::MessageDialogKind::Error)
        .blocking_show();
    close_splash(handle);
    kill_backend(handle);
    handle.exit(1);
}

fn main() {
    reveal::mark_launch();
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![reveal::app_ready])
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            reveal::round_splash(&handle);
            let spawned = match engine_program() {
                Some(program) => start_engine(&program).map_err(|err| engine_start::Failure::NotStarted(err.to_string())),
                None => Err(engine_start::Failure::Missing),
            };
            tauri::async_runtime::spawn(async move {
                let mut tail = engine_start::Tail::default();
                let found = match spawned {
                    Ok((child, rx)) => {
                        if let Ok(mut slot) = handle.state::<Backend>().0.lock() {
                            *slot = Some(child);
                        }
                        read_port(rx, &mut tail).await
                    }
                    Err(failure) => Err(failure),
                };
                let failure = match found {
                    Ok((port, key)) if open_main(&handle, port, key.as_deref()) => {
                        check_for_updates(handle.clone());
                        return;
                    }
                    Ok(_) => engine_start::Failure::Window,
                    Err(failure) => failure,
                };
                engine_failed(&handle, failure, &tail);
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("tauri app should build");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            kill_backend(handle);
        }
    });
}
