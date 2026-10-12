import type { Ctx } from '../../app';
import { Dialog } from '../../ui/dialogs';
import { el, q, setText } from '../../ui/dom';
import { toast } from '../../ui/toast';
import { events } from '../../io/events';

type Choice = 'allow' | 'later' | 'block';
interface Status { outsideAgents: string; pending: Array<{ client: string; channel: string }> }

class AgentConsent extends Dialog {
  private readonly who = el('<strong></strong>');
  private readonly later: HTMLButtonElement;
  private done = false;

  constructor(private readonly ctx: Ctx) {
    super('AI agent access', 440);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('cv-savechanges');
    const lead = el('<p class="cv-save-q"> wants to use formlit.</p>');
    lead.prepend(this.who);
    this.body.append(lead, el('<p class="cv-note">It can search your catalog, develop photos and export files on this computer with the same commands you use here, and every change can be undone. Deleting files and switching catalogs stay with you. Allow applies to every agent on this computer until you change it in Preferences, AI agents.</p>'));
    this.button('Block', 'ghost', () => this.reply('block')).classList.add('cv-btn-apart');
    this.later = this.button('Not now', 'ghost', () => this.reply('later'));
    this.button('Allow', 'primary', () => this.reply('allow'));
    this.onClose = () => { if (!this.done) this.send('later'); };
  }

  ask(client: string): void {
    if (this.isOpen) return;
    setText(this.who, client);
    this.done = false;
    this.open(this.later);
  }

  dismiss(): void {
    if (!this.isOpen) return;
    this.done = true;
    this.close();
  }

  private reply(choice: Choice): void {
    this.done = true;
    this.close();
    this.send(choice);
  }

  private send(choice: Choice): void {
    void this.ctx.api.cmd('agents.respond', { choice }).then(() => {
      if (choice !== 'later') toast(`AI agents ${choice === 'allow' ? 'allowed' : 'blocked'}. Change this in Preferences, AI agents.`);
    }, (err) => this.ctx.fail(err));
  }
}

export function registerAgentConsent(ctx: Ctx): void {
  let dialog: AgentConsent | null = null;
  const show = (client: string): void => {
    dialog ??= new AgentConsent(ctx);
    dialog.ask(client === 'an outside agent' ? 'An outside agent' : client);
  };
  events.on('agents.consent', (e) => show(String(e.client ?? 'An outside agent')));
  events.on('agents.changed', (e) => { if (e.outsideAgents !== 'ask' || e.choice === 'later') dialog?.dismiss(); });
  const pull = (): void => {
    void ctx.api.cmd<Status>('agents.status').then((s) => {
      const first = s.pending[0];
      if (first && s.outsideAgents === 'ask') show(first.client);
    }, () => undefined);
  };
  events.on('hello', pull);
  events.on('resync', pull);
}
