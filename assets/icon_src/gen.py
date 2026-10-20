import math, sys
from shapely.geometry import Point, Polygon

def squircle(cx, cy, size, n=3.0, pts=90):
    e = 0.30*size; h = size/2
    corners = [(cx+h-e, cy-h+e, 0), (cx+h-e, cy+h-e, 90), (cx-h+e, cy+h-e, 180), (cx-h+e, cy-h+e, 270)]
    out=[]
    for (ox, oy, start) in corners:
        for i in range(pts+1):
            t = math.radians(start - 90 + 90*i/pts)
            c, s_ = math.cos(t), math.sin(t)
            out.append(f"{ox+e*math.copysign(abs(c)**(2/n),c):.2f},{oy+e*math.copysign(abs(s_)**(2/n),s_):.2f}")
    return "M"+" L".join(out)+" Z"
RRECT = "M230,0 H794 A230,230 0 0 1 1024,230 V794 A230,230 0 0 1 794,1024 H230 A230,230 0 0 1 0,794 V230 A230,230 0 0 1 230,0 Z"
STOPS = [(0,(0x3A,0x7B,0xFF)),(0.32,(0x9A,0x5C,0xFF)),(0.64,(0xFF,0x4F,0x7A)),(1,(0xFF,0xAE,0x2B))]
def grad(t):
    for (a,ca),(b,cb) in zip(STOPS,STOPS[1:]):
        if t<=b:
            u=(t-a)/(b-a); return tuple(round(ca[i]+(cb[i]-ca[i])*u) for i in range(3))
    return STOPS[-1][1]
hexc = lambda c: "#%02X%02X%02X" % c
pth = lambda poly: "M" + " L".join(f"{x:.1f},{y:.1f}" for x,y in list(poly.exterior.coords)[:-1]) + " Z"

def blades(cx, cy, R, r, N=7, rot=-12, gap=5):
    P = [(cx + r*math.cos(math.radians(rot + 360*i/N)), cy + r*math.sin(math.radians(rot + 360*i/N))) for i in range(N)]
    disk = Point(cx, cy).buffer(R, quad_segs=64)
    out = []
    for i in range(N):
        a, b, c = P[i], P[(i+1)%N], P[(i+2)%N]
        d1 = (b[0]-a[0], b[1]-a[1]); d2 = (c[0]-b[0], c[1]-b[1])
        far = 4*R
        n1 = math.hypot(*d1); n2 = math.hypot(*d2)
        w = Polygon([b, (b[0]+d1[0]/n1*far, b[1]+d1[1]/n1*far),
                     (b[0]+(d1[0]/n1+d2[0]/n2)*far, b[1]+(d1[1]/n1+d2[1]/n2)*far),
                     (b[0]+d2[0]/n2*far, b[1]+d2[1]/n2*far)])
        blade = w.intersection(disk).buffer(-gap/2, join_style=2).buffer(gap*0.15, join_style=1)
        ang = math.degrees(math.atan2((b[1]+c[1])/2-cy, (b[0]+c[0])/2-cx))
        out.append((blade, ang))
    return out, P

def bokeh_defs(P, items):
    d = ''
    for i,(x,y,rad,col,op) in enumerate(items):
        lite = hexc(tuple(round(v+(255-v)*0.35) for v in col)); c = hexc(col); rimc = hexc(tuple(round(v+(255-v)*0.6) for v in col))
        d += (f'<radialGradient id="{P}bk{i}" cx="0.5" cy="0.5" r="0.5">'
              f'<stop offset="0" stop-color="{lite}" stop-opacity="{op*0.55:.2f}"/>'
              f'<stop offset="0.7" stop-color="{c}" stop-opacity="{op*0.62:.2f}"/>'
              f'<stop offset="0.9" stop-color="{rimc}" stop-opacity="{op*0.95:.2f}"/>'
              f'<stop offset="0.96" stop-color="{c}" stop-opacity="{op*0.5:.2f}"/>'
              f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    return d

def svg(mode="mac", detail="full", P="", compact=False):
    T = 824 if mode=="mac" else 1024
    k = 1.0 if mode=="mac" else 1.08
    if mode!="mac" and detail=="simple": k = 1.0
    simple = detail=="simple"
    tile = RRECT if compact else squircle(512,512,T)
    cx, cy = 512 - 6*k, 512 + 10*k
    Ro = (292 if not simple else 318)*k           # barrel outer
    Rb = Ro - (34 if not simple else 40)*k        # glass / blade disk
    ro = (78 if not simple else 70)*k             # opening
    bl, Pp = blades(cx, cy, Rb, ro, gap=(6 if not simple else 9)*k)
    # bokeh: soft discs with bright rims, out of focus behind and around the lens
    bk = [] if simple else [
        (cx+Ro*0.80, cy-Ro*1.02, 92*k, grad(1.0), 0.95),
        (cx+Ro*1.08, cy-Ro*0.62, 54*k, grad(0.75), 0.85),
        (cx+Ro*0.40, cy-Ro*1.20, 40*k, grad(0.9), 0.70),
        (cx-Ro*0.90, cy+Ro*0.76, 64*k, grad(0.15), 0.85),
        (cx-Ro*0.50, cy+Ro*1.03, 40*k, grad(0.35), 0.70),
        (cx-Ro*1.10, cy+Ro*0.38, 30*k, grad(0.05), 0.65),
    ]
    if simple:
        bk = [(cx+Ro*0.82, cy-Ro*0.96, 92*k, grad(1.0), 1.0), (cx-Ro*0.98, cy+Ro*0.86, 60*k, grad(0.2), 0.9)]
    g=[f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
<defs>
 <linearGradient id="{P}bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#24212B"/><stop offset="1" stop-color="#0B0A0E"/></linearGradient>
 <radialGradient id="{P}bloom" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#FF4F7A" stop-opacity="0.26"/><stop offset="0.25" stop-color="#C255D9" stop-opacity="0.15"/><stop offset="0.5" stop-color="#9A5CFF" stop-opacity="0.07"/><stop offset="1" stop-color="#9A5CFF" stop-opacity="0"/></radialGradient>
 <linearGradient id="{P}rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.22"/><stop offset="0.3" stop-color="#fff" stop-opacity="0.04"/><stop offset="1" stop-color="#fff" stop-opacity="0.08"/></linearGradient>
 <linearGradient id="{P}paint" gradientUnits="userSpaceOnUse" x1="{cx-Rb:.0f}" y1="{cy+Rb:.0f}" x2="{cx+Rb:.0f}" y2="{cy-Rb:.0f}"><stop offset="0" stop-color="#3A7BFF"/><stop offset="0.32" stop-color="#9A5CFF"/><stop offset="0.64" stop-color="#FF4F7A"/><stop offset="1" stop-color="#FFAE2B"/></linearGradient>
 <linearGradient id="{P}barrel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4A4655"/><stop offset="0.45" stop-color="#25222C"/><stop offset="1" stop-color="#121016"/></linearGradient>
 <linearGradient id="{P}chamfer" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.65"/><stop offset="0.5" stop-color="#fff" stop-opacity="0.08"/><stop offset="1" stop-color="#fff" stop-opacity="0.30"/></linearGradient>
 <radialGradient id="{P}hole" cx="0.42" cy="0.40" r="0.62"><stop offset="0" stop-color="#2B1B45"/><stop offset="0.6" stop-color="#0F0A18"/><stop offset="1" stop-color="#050308"/></radialGradient>
 <linearGradient id="{P}gloss" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.42"/><stop offset="0.45" stop-color="#fff" stop-opacity="0.04"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
 <radialGradient id="{P}vign" cx="0.5" cy="0.5" r="0.5"><stop offset="0.62" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.45"/></radialGradient>
 {bokeh_defs(P, bk)}
 <filter id="{P}tileshadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#000" flood-opacity="0.5"/></filter>
 <filter id="{P}lensshadow" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="{18*k:.1f}" stdDeviation="{24*k:.1f}" flood-color="#000" flood-opacity="0.6"/></filter>
 <filter id="{P}soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="{4.8*k:.1f}"/></filter>
 <clipPath id="{P}tclip"><path d="{tile}"/></clipPath>
 <clipPath id="{P}glass"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Rb:.1f}"/></clipPath>
</defs>''']
    if mode=="mac" and not compact: g.append(f'<path d="{tile}" fill="#000" filter="url(#{P}tileshadow)"/>')
    g.append(f'<path d="{tile}" fill="url(#{P}bg)"/>')
    g.append(f'<g clip-path="url(#{P}tclip)"><rect width="1024" height="1024" fill="url(#{P}bloom)"/>')
    soft = '' if compact else f' filter="url(#{P}soft)"'
    for i,(x,y,rad,col,op) in enumerate(bk):
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="url(#{P}bk{i})" style="mix-blend-mode:screen"{soft}/>')
    g.append('</g>')
    # lens barrel
    sh = '' if compact else f' filter="url(#{P}lensshadow)"'
    if compact: g.append(f'<circle cx="{cx:.1f}" cy="{cy+12*k:.1f}" r="{Ro:.1f}" fill="#000" fill-opacity=".4"/>')
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Ro:.1f}" fill="url(#{P}barrel)"{sh}/>')
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Ro-1.5*k:.1f}" fill="none" stroke="url(#{P}chamfer)" stroke-width="{3*k:.1f}"/>')
    if not simple:
        g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{(Ro+Rb)/2:.1f}" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="{2*k:.1f}"/>')
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Rb+3*k:.1f}" fill="#06040A"/>')
    # iris
    g.append(f'<g clip-path="url(#{P}glass)">')
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Rb:.1f}" fill="url(#{P}hole)"/>')
    for blade, ang in bl:
        d = pth(blade)
        light = 0.5 + 0.5*math.cos(math.radians(ang + 135))      # key light from the top left
        g.append(f'<path d="{d}" fill="url(#{P}paint)"/>')
        g.append(f'<path d="{d}" fill="{"#FFFFFF" if light>0.5 else "#0A0410"}" fill-opacity="{abs(light-0.5)*0.62:.3f}"/>')
    # opening: deep glass with a coloured glint
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Rb:.1f}" fill="url(#{P}vign)"/>')
    g.append(f'<circle cx="{cx-ro*0.28:.1f}" cy="{cy-ro*0.30:.1f}" r="{ro*0.22:.1f}" fill="#9A5CFF" fill-opacity=".55"{soft}/>')
    # glass reflection: a crescent and a small streak
    gr = Rb*0.96
    g.append(f'<path d="M{cx-gr*0.92:.1f},{cy-gr*0.12:.1f} A{gr:.1f},{gr:.1f} 0 0 1 {cx+gr*0.30:.1f},{cy-gr*0.95:.1f} A{gr*1.35:.1f},{gr*1.35:.1f} 0 0 0 {cx-gr*0.92:.1f},{cy-gr*0.12:.1f} Z" fill="url(#{P}gloss)"/>')
    if not simple:
        g.append(f'<path d="M{cx+gr*0.52:.1f},{cy+gr*0.50:.1f} A{gr*0.78:.1f},{gr*0.78:.1f} 0 0 0 {cx+gr*0.74:.1f},{cy+gr*0.12:.1f}" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="{7*k:.1f}" stroke-linecap="round"/>')
    g.append('</g>')
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{Rb:.1f}" fill="none" stroke="#fff" stroke-opacity=".16" stroke-width="{2*k:.1f}"/>')
    # one bokeh disc drifting in front of the lens edge, top right
    if not simple:
        x,y,rad,col,op = (cx+Ro*0.70, cy-Ro*0.76, 40*k, grad(0.85), 0.75)
        g[0] = g[0].replace('</defs>', bokeh_defs(P+'f', [(x,y,rad,col,op)]) + '</defs>')
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="url(#{P}fbk0)" style="mix-blend-mode:screen"{soft}/>')
    g.append(f'<path d="{tile}" fill="none" stroke="url(#{P}rim)" stroke-width="{3*(T/824):.1f}" clip-path="url(#{P}tclip)"/>')
    g.append('</svg>')
    return "\n".join(g)

if __name__=="__main__":
    open(sys.argv[3],"w").write(svg(sys.argv[1], sys.argv[2]))
