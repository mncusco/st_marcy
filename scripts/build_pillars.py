# -*- coding: utf-8 -*-
"""ShamanicTravels — editoriale pillar generator.
Reads scripts/pillar_template.html, expands tokens, writes insights/<key>.html.
"""
import os, io, sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(SITE, "scripts", "pillar_template.html")
OUT_DIR = os.path.join(SITE, "insights")

PILLARS = [
    {
        "key": "ayahuasca-safety",
        "title": "Ayahuasca & Safety",
        "h1": "Ayahuasca & Safety",
        "intro": "What the experience is, what it is not, and what responsible participation requires. Screening, preparation, environment, consent, and the distinction between an experience of consciousness and clinical care — discussed soberly, without promise or spectacle.",
        "cta": "If you are considering an experience of this kind, discover how we work.",
        "cta_link": "/amazon_clean",
        "cta_link_label": "Amazon · San Alejandro",
        "image": "jungle.jpg",
        "related": ["ethics-shamanism", "preparation-integration", "amazon"],
    },
    {
        "key": "preparation-integration",
        "title": "Preparation & Integration",
        "h1": "Preparation & Integration",
        "intro": "The months before and the weeks after matter as much as the experience itself. What responsible engagement looks like: preparation of body and mind, honest expectations, and the patient work of returning to ordinary life.",
        "cta": "Discover how preparation is built into every journey we curate.",
        "cta_link": "/amazon_clean",
        "cta_link_label": "Amazon · San Alejandro",
        "image": "inner-journey.jpg",
        "related": ["ayahuasca-safety", "lifestyle-ethos"],
    },
    {
        "key": "ethics-shamanism",
        "title": "Ethics & Shamanism",
        "h1": "Ethics & Shamanism",
        "intro": "Language, respect, consent, and the relationship between visitor and tradition. A sober look at cultural authenticity, the burden of the word \u201cshaman\u201d, and the difference between an authentic encounter and a constructed product.",
        "cta": "These are the questions we ask ourselves before every journey.",
        "cta_link": "/landing-editorial",
        "cta_link_label": "Editorial introduction",
        "image": "insights.jpg",
        "related": ["ayahuasca-safety", "peru"],
    },
    {
        "key": "peru",
        "title": "Peru",
        "h1": "Peru",
        "intro": "Machu Picchu, the Sacred Valley, Cusco, Lake Titicaca \u2014 and the living culture between them. Destination notes beyond the standardised itinerary, written with the restraint of a place that has little interest in performance.",
        "cta": "Discover how we build private journeys through Peru.",
        "cta_link": "/andean_arc_clean",
        "cta_link_label": "Andean Arc",
        "image": "hero-machu-picchu.jpg",
        "related": ["andes", "amazon", "private-journeys"],
    },
    {
        "key": "amazon",
        "title": "Amazon",
        "h1": "Amazon",
        "intro": "The Peruvian Amazon as a place of tradition, isolation and honesty. San Alejandro, the Ucayali, and what it means to enter a world that operates on its own terms.",
        "cta": "Discover how we build a private Amazon experience.",
        "cta_link": "/amazon_clean",
        "cta_link_label": "San Alejandro · Amazon",
        "image": "amazon.jpg",
        "related": ["ayahuasca-safety", "peru", "preparation-integration"],
    },
    {
        "key": "andes",
        "title": "Andes",
        "h1": "Andes",
        "intro": "The Andes as geography, culture and inner terrain. High-altitude paths, Andean tradition, and what changes when the landscape removes every pretext for haste.",
        "cta": "Discover the Andean Arc, a twenty-one-day private expedition.",
        "cta_link": "/andean_arc_clean",
        "cta_link_label": "Andean Arc",
        "image": "andean-arc.jpg",
        "related": ["peru", "ethics-shamanism"],
    },
    {
        "key": "private-journeys",
        "title": "Private Journeys",
        "h1": "Private Journeys",
        "intro": "What changes when an experience is private. Six participants. One guide. A conversation that precedes any itinerary. Selection, time, silence and attention as working materials.",
        "cta": "If you are considering a journey of this kind, discover how to begin.",
        "cta_link": "/apply_clean",
        "cta_link_label": "Begin with a conversation",
        "image": "hero.jpg",
        "related": ["peru", "andes", "amazon"],
    },
    {
        "key": "lifestyle-ethos",
        "title": "Lifestyle & Ethos",
        "h1": "Lifestyle & Ethos",
        "intro": "The luxury of subtraction. Solitude, time, attention, and the difference between travelling and being moved. Notes on why the absence of everything unnecessary is itself the experience.",
        "cta": "Explore the editorial introduction to the philosophy behind ShamanicTravels.",
        "cta_link": "/landing-editorial",
        "cta_link_label": "Editorial introduction",
        "image": "stonework.jpg",
        "related": ["private-journeys", "preparation-integration"],
    },
]

LABELS = {p["key"]: p["title"] for p in PILLARS}


def related_html(keys):
    links = "".join(
        '<a href="/insights/{k}" class="eyebrow">{label}</a>'.format(k=k, label=LABELS[k])
        for k in keys
    )
    return (
        '<div class="pillar-related">\n'
        '  <span class="eyebrow pillar-related-label">Related collections</span>\n'
        '  <div class="pillar-related-links">{links}</div>\n'
        '</div>'
    ).format(links=links)


def main():
    with io.open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()

    els = os.listdir(OUT_DIR) if os.path.isdir(OUT_DIR) else []
    stale = [os.path.join(OUT_DIR, e) for e in els if e.endswith(".html")]

    for p in PILLARS:
        out = tpl
        for token in ("__KEY__", "__TITLE__", "__H1__", "__INTRO__",
                      "__CTA__", "__CTA_LINK__", "__CTA_LINK_LABEL__", "__IMAGE__"):
            out = out.replace(token, p[token.replace("__", "").lower()])
        out = out.replace("__RELATED_HTML__", related_html(p["related"]))
        path = os.path.join(OUT_DIR, p["key"] + ".html")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(out)
        print("wrote", path)

    for bad in stale:
        print("stale (keep?):", bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())