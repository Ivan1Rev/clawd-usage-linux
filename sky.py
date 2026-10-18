"""Sky behind Clawd: time-of-day gradient, sun and moon on an arc, stars, drifting
pixel clouds, fog, rain, snow and lightning from the real weather.

Port of lib/sky.ps1 and lib/weather.ps1 from clawd-usage-winwidget (MIT).
Weather: Open-Meteo (no key), falling back to met.no; location from the config
or once per run by IP via ipwho.is.
"""

import json
import math
import random
import threading
import time
import urllib.request
from datetime import datetime, timezone

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient


def argb(h):
    """'#AARRGGBB' -> (a, r, g, b)."""
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))


def mix(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(4))


def dim(c, g):
    """Cloudiness: colour fades toward grey and darkens."""
    a, r, gg, b = c
    lum = 0.3 * r + 0.59 * gg + 0.11 * b
    f = 1 - 0.3 * g
    return (a, int((r + (lum - r) * g) * f), int((gg + (lum - gg) * g) * f), int((b + (lum - b) * g) * f))


def qc(c, opacity=1.0):
    return QColor(c[1], c[2], c[3], max(0, min(255, int(c[0] * opacity))))


PAL = {
    'night': {'top': argb('#00304A8C'), 'bottom': argb('#1A304A8C'), 'light': 0.0},
    'dawn':  {'top': argb('#00404E8A'), 'bottom': argb('#33E08A66'), 'light': 0.5},
    'day':   {'top': argb('#004A8CCB'), 'bottom': argb('#2E6FA8D8'), 'light': 1.0},
    'dusk':  {'top': argb('#00383070'), 'bottom': argb('#33D86A50'), 'light': 0.5},
}
SUN_HIGH, SUN_LOW = argb('#FFFDE68A'), argb('#FFFB923C')
SNOW_DAY, SNOW_NIGHT = argb('#80DDE4EC'), argb('#50A1A8B5')
CLOUD_DAY, CLOUD_NIGHT, CLOUD_RAIN = argb('#FFB4B4BC'), argb('#FF5E5E68'), argb('#FF52525B')

SUN_ART = ['..###..', '.#####.', '#######', '#######', '#######', '.#####.', '..###..']
CLOUD_SHAPES = [
    ['....###.....', '..#######...', '.##########.', '############'],
    ['..###...', '.######.', '########'],
    ['...##.##..', '.########.', '##########'],
]

# WMO weather codes: cover 0..1, drops/flakes at medium intensity.
KINDS = [
    ((0,), 'clear', 0.0, {}), ((1,), 'mostly clear', 0.2, {}), ((2,), 'partly cloudy', 0.5, {}),
    ((3,), 'overcast', 0.85, {}), ((45, 48), 'fog', 0.7, {'fog': True}),
    ((51, 53, 55), 'drizzle', 0.8, {'rain': 6}), ((56, 57), 'freezing drizzle', 0.8, {'rain': 6}),
    ((61, 63, 65), 'rain', 0.9, {'rain': 12}), ((66, 67), 'freezing rain', 0.9, {'rain': 12}),
    ((71, 73, 75), 'snow', 0.85, {'snow': 10}), ((77,), 'snow grains', 0.85, {'snow': 8}),
    ((80, 81, 82), 'showers', 0.85, {'rain': 16}), ((85, 86), 'snow showers', 0.9, {'snow': 14}),
    ((95, 96, 99), 'thunderstorm', 1.0, {'rain': 16, 'storm': True}),
]


def weather_kind(code):
    for codes, name, cover, extra in KINDS:
        if code in codes:
            i = codes.index(code)
            mul = (0.6, 1.0, 1.35)[i] if len(codes) == 3 else 1.0
            return {'name': name, 'cover': cover, 'fog': extra.get('fog', False),
                    'storm': extra.get('storm', False),
                    'rain': round(extra.get('rain', 0) * mul), 'snow': round(extra.get('snow', 0) * mul)}
    return {'name': f'code {code}', 'cover': 0.5, 'fog': False, 'storm': False, 'rain': 0, 'snow': 0}


def sun_calc(lat, lon):
    """Sunrise/sunset (NOAA), local minutes from midnight."""
    now = datetime.now()
    gm = 2 * math.pi / 365 * (now.timetuple().tm_yday - 0.5)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(gm) - 0.032077 * math.sin(gm) -
                   0.014615 * math.cos(2 * gm) - 0.040849 * math.sin(2 * gm))
    dec = (0.006918 - 0.399912 * math.cos(gm) + 0.070257 * math.sin(gm) -
           0.006758 * math.cos(2 * gm) + 0.000907 * math.sin(2 * gm) -
           0.002697 * math.cos(3 * gm) + 0.00148 * math.sin(3 * gm))
    la = math.radians(lat)
    c = math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(dec)) - math.tan(la) * math.tan(dec)
    c = max(-0.999, min(0.999, c))
    ha = math.degrees(math.acos(c))
    tz = now.astimezone().utcoffset().total_seconds() / 60
    return {'sr': ((720 - 4 * (lon + ha) - eq + tz) % 1440 + 1440) % 1440,
            'ss': ((720 - 4 * (lon - ha) - eq + tz) % 1440 + 1440) % 1440}


def metno_code(sym):
    import re
    sym = re.sub(r'_(day|night|polartwilight)$', '', sym or '')
    lvl = 0 if sym.startswith('light') else (2 if sym.startswith('heavy') else 1)
    shw = 'showers' in sym
    if 'thunder' in sym:
        return 95
    if 'snow' in sym:
        return (85, 85, 86)[lvl] if shw else (71, 73, 75)[lvl]
    if 'sleet' in sym:
        return 67 if lvl == 2 else 66
    if 'rain' in sym:
        return (80, 81, 82)[lvl] if shw else (61, 63, 65)[lvl]
    for pre, code in (('fog', 45), ('cloudy', 3), ('partlycloudy', 2), ('fair', 1), ('clearsky', 0)):
        if sym.startswith(pre):
            return code
    return 3


def _get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'clawd-usage-linux'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


class Weather:
    """Fetches location (once) and weather in a worker thread."""

    def __init__(self):
        self.geo = None          # {'lat', 'lon', 'city'} from IP
        self.wx = None           # {'code','temp','wind','sunrise','sunset','at'}
        self.alt = False         # Open-Meteo failed - use met.no
        self.last_try = 0.0
        self.geo_try = 0.0
        self.thread = None

    def place(self, cfg):
        try:
            if cfg.get('weatherLat') not in (None, '') and cfg.get('weatherLon') not in (None, ''):
                return {'lat': float(cfg['weatherLat']), 'lon': float(cfg['weatherLon']), 'city': None}
        except (TypeError, ValueError):
            pass
        return self.geo

    def due(self, cfg):
        if self.thread and self.thread.is_alive():
            return False
        return time.time() - self.last_try >= float(cfg.get('weatherIntervalSeconds', 900))

    def start(self, cfg):
        self.last_try = time.time()
        place = self.place(cfg)

        def run():
            p = place
            if not p:
                if time.time() - self.geo_try < 600:
                    return
                self.geo_try = time.time()
                try:
                    j = _get_json('https://ipwho.is/')
                    if j.get('success') is not False and j.get('latitude') is not None:
                        self.geo = p = {'lat': float(j['latitude']), 'lon': float(j['longitude']),
                                        'city': j.get('city')}
                except Exception:
                    return
            for attempt in range(2):
                try:
                    if not self.alt:
                        j = _get_json(
                            f'https://api.open-meteo.com/v1/forecast?latitude={p["lat"]}&longitude={p["lon"]}'
                            '&current=weather_code,temperature_2m,wind_speed_10m'
                            '&daily=sunrise,sunset&timezone=auto&forecast_days=1')
                        cur = j['current']
                        wx = {'code': int(cur['weather_code']), 'temp': float(cur['temperature_2m']),
                              'wind': float(cur['wind_speed_10m']), 'sunrise': None, 'sunset': None,
                              'at': time.time()}
                        try:
                            sr = datetime.strptime(j['daily']['sunrise'][0], '%Y-%m-%dT%H:%M')
                            ss = datetime.strptime(j['daily']['sunset'][0], '%Y-%m-%dT%H:%M')
                            wx['sunrise'] = sr.hour * 60 + sr.minute
                            wx['sunset'] = ss.hour * 60 + ss.minute
                        except Exception:
                            pass
                    else:
                        j = _get_json('https://api.met.no/weatherapi/locationforecast/2.0/compact'
                                      f'?lat={p["lat"]:.4f}&lon={p["lon"]:.4f}')
                        d = j['properties']['timeseries'][0]['data']
                        wx = {'code': metno_code(d.get('next_1_hours', {}).get('summary', {}).get('symbol_code')),
                              'temp': float(d['instant']['details']['air_temperature']),
                              'wind': 3.6 * float(d['instant']['details']['wind_speed']),
                              'sunrise': None, 'sunset': None, 'at': time.time()}
                    self.wx = wx
                    return
                except Exception:
                    if self.alt:
                        return
                    self.alt = True   # Open-Meteo unreachable - ask met.no
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def current(self):
        wx = self.wx
        if wx and time.time() - wx['at'] < 3 * 3600:
            return wx
        return None

    def sun_times(self, cfg):
        wx = self.wx
        if wx and wx.get('sunrise') is not None and wx.get('sunset') is not None:
            return {'sr': float(wx['sunrise']), 'ss': float(wx['sunset'])}
        p = self.place(cfg)
        if p:
            return sun_calc(p['lat'], p['lon'])
        return {'sr': 420.0, 'ss': 1140.0}

    def tooltip(self, cfg):
        parts = []
        wx = self.current()
        if wx:
            p = self.place(cfg)
            t = round(wx['temp'])
            line = f'{"+" if t > 0 else ""}{t}°, {weather_kind(wx["code"])["name"]}'
            if p and p.get('city'):
                line = f'{p["city"]} · {line}'
            parts.append(line)
            parts.append(f'wind {round(wx["wind"] / 3.6)} m/s')
        else:
            parts.append('no weather data yet')
        st = self.sun_times(cfg)
        fmt = lambda m: f'{int(m // 60) % 24:02d}:{int(m % 60):02d}'
        parts.append(f'sunrise {fmt(st["sr"])} · sunset {fmt(st["ss"])}')
        return '\n'.join(parts)


class Sky:
    def __init__(self, weather, cfg):
        self.weather = weather
        self.cfg = cfg
        self.rnd = random.Random()
        self.w = self.h = 0.0
        self.tick = 0
        self.key = ''
        self.flash = 0
        self.light = 0.0
        self.kind = weather_kind(0)
        self.top = PAL['night']['top']
        self.bottom = PAL['night']['bottom']
        self.cloud_col = CLOUD_DAY
        self.ground = None
        self.sun = None
        self.sun_col = SUN_HIGH
        self.moon = None
        self.moon_key = ''
        self.moon_lit, self.moon_dark = [], []
        self.vis = 1.0
        self.star_op = 0.0
        self.n_clouds = self.n_rain = self.n_snow = 0
        self.stars = [{'fx': self.rnd.random(), 'fy': self.rnd.random() * 0.6} for _ in range(20)]
        self.clouds = []
        for i in range(9):
            rows = CLOUD_SHAPES[i % len(CLOUD_SHAPES)]
            self.clouds.append({'rows': rows, 'w': len(rows[0]) * 2, 'x': -1.0,
                                'fy': 0.05 + 0.3 * self.rnd.random(),
                                'v': 0.7 + 0.6 * self.rnd.random(), 'fade': 0.0})
        self.fog = [{'x': self.rnd.random(), 'fy': 0.42 + 0.2 * i} for i in range(3)]
        self.drops = [{'x': 0.0, 'y': -99.0, 'v': 0.0} for _ in range(40)]
        self.flakes = [{'x': 0.0, 'y': -99.0, 'v': 0.0, 'ph': 0.0} for _ in range(34)]

    # -- moon phase from the mean synodic month since the new moon of 6 Jan 2000 --
    def set_moon_phase(self, lat):
        P = 29.530588853
        ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc).timestamp()
        age = (((time.time() - ref) / 86400) % P + P) % P
        key = f'{round(age * 2)}|{lat < 0}'
        if key == self.moon_key:
            return
        self.moon_key = key
        th = 2 * math.pi * age / P
        k = math.cos(th)
        n, r = 7, 3.5
        lit, dark = [], []
        for y in range(n):
            for x in range(n):
                u = (x + 0.5 - r) / r
                v = (y + 0.5 - r) / r
                if lat < 0:
                    u = -u
                inside = u * u + v * v <= 1.05
                t = k * math.sqrt(max(0, 1 - v * v))
                on = inside and ((u > t) if th < math.pi else (u < -t))
                if on:
                    lit.append((x, y))
                elif inside:
                    dark.append((x, y))
        self.moon_lit, self.moon_dark = lit, dark

    @staticmethod
    def on_arc(p, half, w, h):
        if p < -0.06 or p > 1.06:
            return None
        alt = math.sin(math.pi * p)
        return (7 + p * (w - 14) - half, h + 3 - alt * (h - 12) - half)

    def step(self, w, h):
        self.tick += 1
        if w <= 0 or h <= 0:
            return
        rnd = self.rnd
        if w != self.w or h != self.h:
            self.w, self.h, self.key = w, h, ''
            for c in self.clouds:
                if c['x'] < 0:
                    c['x'] = rnd.random() * w

        st = self.weather.sun_times(self.cfg)
        sr, ss = st['sr'], st['ss']
        now = datetime.now()
        t = now.hour * 60 + now.minute + now.second / 60
        wx = self.weather.current()
        code = int(wx['code']) if wx else int(self.cfg.get('skyDefaultWeather', 2))
        wind = float(wx['wind']) if wx else 8.0

        key = f'{int(t)}|{code}|{w}|{h}'
        if key != self.key:
            self.key = key
            kind = weather_kind(code)
            self.kind = kind
            stops = [(sr - 80, 'night'), (sr - 10, 'dawn'), (sr + 70, 'day'),
                     (ss - 70, 'day'), (ss + 10, 'dusk'), (ss + 80, 'night')]
            a = b = PAL['night']
            k = 0.0
            for i in range(len(stops) - 1):
                if stops[i][0] <= t < stops[i + 1][0]:
                    a, b = PAL[stops[i][1]], PAL[stops[i + 1][1]]
                    k = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0])
                    break
            self.light = a['light'] + (b['light'] - a['light']) * k
            g = kind['cover'] * 0.9
            self.top = dim(mix(a['top'], b['top'], k), g)
            self.bottom = dim(mix(a['bottom'], b['bottom'], k), g)
            self.ground = mix(SNOW_NIGHT, SNOW_DAY, self.light) if kind['snow'] > 0 else None
            cc = mix(CLOUD_NIGHT, CLOUD_DAY, self.light)
            if kind['rain'] or kind['storm']:
                cc = mix(cc, CLOUD_RAIN, 0.55)
            self.cloud_col = cc

            self.vis = max(0.0, 1 - kind['cover'] * 1.15)
            p = (t - sr) / (ss - sr) if ss != sr else 0.5
            self.sun = self.on_arc(p, 4.9, w, h) if self.vis > 0 else None
            if self.sun:
                self.sun_glow = self.on_arc(p, 10, w, h)
                self.sun_col = mix(SUN_LOW, SUN_HIGH, math.sin(math.pi * p) * 1.6)
            place = self.weather.place(self.cfg)
            self.set_moon_phase(place['lat'] if place else 50)
            q = ((t - ss + 1440) % 1440) / (sr + 1440 - ss)
            self.moon = self.on_arc(q, 4.55, w, h) if self.vis > 0 else None

            self.star_op = (1 - self.light * 2) * max(0.0, 1 - kind['cover'] * 1.4)
            dens = max(1.0, w / 140.0)
            self.n_clouds = min(len(self.clouds), round(kind['cover'] * 5 * dens))
            self.n_rain = min(len(self.drops), round(kind['rain'] * dens))
            self.n_snow = min(len(self.flakes), round(kind['snow'] * dens))

        kind = self.kind
        drift = 0.04 + wind / 350.0
        for i, c in enumerate(self.clouds):
            want = 1.0 if i < self.n_clouds else 0.0
            c['fade'] += max(-0.03, min(0.03, want - c['fade']))
            if c['fade'] <= 0:
                continue
            c['x'] += drift * c['v']
            if c['x'] > w:
                c['x'] = -c['w']
                c['fy'] = 0.05 + 0.3 * rnd.random()
        for f in self.fog:
            f['x'] = (f['x'] + 0.0015) % 1.6
        slant = min(1.2, wind / 25.0)
        for i, d in enumerate(self.drops):
            if i >= self.n_rain:
                d['y'] = -99
                continue
            if d['y'] < -50 or d['y'] > h:
                d['x'] = rnd.random() * (w + 10) - 10
                d['y'] = rnd.random() * h if d['y'] < -50 else -4
                d['v'] = 3.5 + 1.5 * rnd.random()
            d['y'] += d['v']
            d['x'] += slant
        self.slant = slant
        for i, f in enumerate(self.flakes):
            if i >= self.n_snow:
                f['y'] = -99
                continue
            if f['y'] < -50 or f['y'] > h:
                f['x'] = rnd.random() * w
                f['y'] = rnd.random() * h if f['y'] < -50 else -2
                f['v'] = 0.3 + 0.35 * rnd.random()
                f['ph'] = rnd.random() * 6.28
            f['y'] += f['v']
        if kind['storm'] and self.flash <= 0 and rnd.randrange(140) == 0:
            self.flash = 7
        self.flash_op = 0.0
        if self.flash > 0:
            self.flash_op = (0, 0.18, 0.05, 0, 0.25, 0.1, 0.04)[self.flash - 1]
            self.flash -= 1

    def paint(self, p, w, h, s):
        """Paint into QPainter p over a w x h (units) area, scale s, with soft edges."""
        if w <= 0 or h <= 0 or not self.key:
            return
        img = QImage(max(1, round(w * s)), max(1, round(h * s)), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        q.scale(s, s)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, qc(self.top))
        grad.setColorAt(1, qc(self.bottom))
        q.fillRect(QRectF(0, 0, w, h), grad)
        q.setPen(Qt.PenStyle.NoPen)
        fx = 0.7   # SkyFx canvas opacity in the original

        def rect(x, y, ww, hh, col, op=1.0):
            q.setBrush(qc(col, op * fx))
            q.drawRect(QRectF(x, y, ww, hh))

        if self.star_op > 0:
            for i, st in enumerate(self.stars):
                op = self.star_op * (0.55 + 0.45 * math.sin(self.tick / 7.0 + i * 1.7))
                rect(round(st['fx'] * (w - 2)), round(2 + st['fy'] * h), 1.2, 1.2, argb('#FFF8FAFC'), max(0, op))
        if self.moon:
            mx, my = self.moon
            for x, y in self.moon_dark:
                rect(mx + x * 1.3, my + y * 1.3, 1.3, 1.3, argb('#2EE5E7EB'), self.vis)
            for x, y in self.moon_lit:
                rect(mx + x * 1.3, my + y * 1.3, 1.3, 1.3, argb('#FFF1F5F9'), self.vis)
        if self.sun:
            gx, gy = self.sun_glow
            rg = QRadialGradient(QPointF(gx + 10, gy + 10), 10)
            rg.setColorAt(0, qc(argb('#40FDE68A'), self.vis * fx))
            rg.setColorAt(1, qc(argb('#00FDE68A')))
            q.setBrush(rg)
            q.drawEllipse(QRectF(gx, gy, 20, 20))
            sx, sy = self.sun
            for y, row in enumerate(SUN_ART):
                for x, ch in enumerate(row):
                    if ch == '#':
                        rect(sx + x * 1.4, sy + y * 1.4, 1.45, 1.45, self.sun_col, self.vis)
        for c in self.clouds:
            if c['fade'] <= 0:
                continue
            cx, cy = round(c['x']), round(c['fy'] * h)
            for y, row in enumerate(c['rows']):
                for x, ch in enumerate(row):
                    if ch == '#':
                        rect(cx + x * 2, cy + y * 2, 2.05, 2.05, self.cloud_col, 0.65 * c['fade'])
        if self.kind['fog']:
            for f in self.fog:
                fw = w * 0.6
                lg = QLinearGradient((f['x'] - 0.6) * w, 0, (f['x'] - 0.6) * w + fw, 0)
                op = (0.14 + 0.05 * math.sin(self.tick / 20.0 + f['fy'] * 10)) * fx
                lg.setColorAt(0, QColor(229, 231, 235, 0))
                lg.setColorAt(0.5, QColor(229, 231, 235, int(255 * op)))
                lg.setColorAt(1, QColor(229, 231, 235, 0))
                q.fillRect(QRectF((f['x'] - 0.6) * w, f['fy'] * h, fw, 3), lg)
        for i, d in enumerate(self.drops[:self.n_rain]):
            rect(d['x'], d['y'], 1, 3.5, argb('#8093C5FD'))
        for f in self.flakes[:self.n_snow]:
            rect(f['x'] + 1.5 * math.sin(self.tick / 9.0 + f['ph']) + self.slant * f['y'] / 4,
                 f['y'], 1.6, 1.6, argb('#C0E4E4E7'))
        if self.ground:
            rect(0, h - 1.5, w, 1.5, self.ground)
        if self.flash_op > 0:
            rect(0, 0, w, h, argb('#FFF8FAFC'), self.flash_op / fx)

        # Soft left and right edges (opacity mask 0 -> 1 at 10%, 1 -> 0 at 90%).
        q.resetTransform()
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        mask = QLinearGradient(0, 0, img.width(), 0)
        mask.setColorAt(0, QColor(0, 0, 0, 0))
        mask.setColorAt(0.1, QColor(0, 0, 0, 255))
        mask.setColorAt(0.9, QColor(0, 0, 0, 255))
        mask.setColorAt(1, QColor(0, 0, 0, 0))
        q.fillRect(img.rect(), mask)
        q.end()
        p.drawImage(QPointF(0, 0), img)
