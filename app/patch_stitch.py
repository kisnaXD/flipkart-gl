from pathlib import Path
import re

def patch_scenarios():
    p = Path(__file__).resolve().parent / "templates" / "stitch" / "scenarios.html"
    html = p.read_text(encoding="utf-8")
    html = re.sub(
        r'<div class="flex-1 overflow-y-auto p-4 space-y-unit custom-scrollbar">.*?</div>\s*</section>\s*<!-- Right Panel',
        '<div id="gl-scenario-cards" class="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar"></div></section><!-- Right Panel',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- Detail Scrollable Content -->.*?</section>\s*</main>",
        '<div id="gl-scenario-detail" class="flex-1 overflow-y-auto p-panel-padding custom-scrollbar"></div></section></main>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    if "gridlock-app.js" not in html:
        html = html.replace(
            "</body></html>",
            '<script>window.GRIDLOCK_PAGE="scenarios";</script><script src="/static/js/gridlock-app.js"></script></body></html>',
        )
    p.write_text(html, encoding="utf-8")


def patch_hotspots():
    p = Path(__file__).resolve().parent / "templates" / "stitch" / "hotspots.html"
    html = p.read_text(encoding="utf-8")
    html = re.sub(
        r"<tbody>.*?</tbody>",
        '<tbody id="gl-hotspot-list"></tbody>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    # add hour slider id if missing - inject before table
    if "gl-hour-slider" not in html:
        html = html.replace(
            "Corridor Risk Ranking",
            'Corridor Risk Ranking <span id="gl-hour-label" class="font-mono-data text-primary ml-2">18:00</span>',
        )
        html = html.replace(
            "Recalculate",
            'Recalculate</button></div><input id="gl-hour-slider" type="range" min="0" max="23" value="18" class="timeline-slider w-48 ml-4" /><div class="hidden">',
        )
    for old, new in [
        ('href="#">Command', 'href="/">Command'),
        ('href="#">Live Map', 'href="/map">Live Map'),
        ('href="#">Scenarios', 'href="/scenarios">Scenarios'),
        ('href="#">Analytics', 'href="/analytics">Analytics'),
        ('href="#">Learning Loop', 'href="/learning">Learning Loop'),
    ]:
        html = html.replace(old, new)
    if "gridlock-app.js" not in html:
        html = html.replace(
            "</body>",
            '<script>window.GRIDLOCK_PAGE="hotspots";</script><script src="/static/js/gridlock-app.js"></script></body>',
        )
    p.write_text(html, encoding="utf-8")


def patch_analytics():
    p = Path(__file__).resolve().parent / "templates" / "stitch" / "analytics.html"
    html = p.read_text(encoding="utf-8")
    html = html.replace(
        '<span class="font-mono-data text-[24px] font-bold text-on-surface">3.2k</span>',
        '<span id="gl-total-events" class="font-mono-data text-[24px] font-bold text-on-surface">—</span>',
    )
    html = html.replace(
        '<span class="font-display-lg text-[56px] leading-[56px] font-bold text-on-surface tracking-tighter">69',
        '<span id="gl-tier-accuracy" class="font-display-lg text-[56px] leading-[56px] font-bold text-on-surface tracking-tighter">69',
    )
    html = html.replace(
        "Duration MAE",
        'Duration MAE <span id="gl-duration-mae" class="text-primary">—</span>',
    )
    for old, new in [
        ('href="#">Command', 'href="/">Command'),
        ('href="#">Live Map', 'href="/map">Live Map'),
        ('href="#">Scenarios', 'href="/scenarios">Scenarios'),
        ('href="#">Hotspots', 'href="/hotspots">Hotspots'),
        ('href="#">Learning Loop', 'href="/learning">Learning Loop'),
    ]:
        html = html.replace(old, new)
    if "gridlock-app.js" not in html:
        html = html.replace(
            "</body>",
            '<script>window.GRIDLOCK_PAGE="analytics";</script><script src="/static/js/gridlock-app.js"></script></body>',
        )
    p.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch_scenarios()
    patch_hotspots()
    patch_analytics()
    print("done")
