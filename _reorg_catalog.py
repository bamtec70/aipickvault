# -*- coding: utf-8 -*-
"""Rewrite PRODUCT_CATALOG with strict category placement + new products."""
from pathlib import Path

path = Path(r"C:\Users\bamte\aipickvault\index.html")
text = path.read_text(encoding="utf-8")

# Update category blurbs to match tighter scope
old_cats = '''        const CATEGORIES = [
          {
            id: "tools",
            name: "Tools & DIY",
            blurb: "Drills, impact kits, pruning saws",
            icon: "fa-tools",
            color: "orange",
            iconBg: "bg-orange-500/10 text-orange-400"
          },
          {
            id: "gig",
            name: "Gig & Delivery",
            blurb: "Power banks, van gear, all-day battery",
            icon: "fa-truck",
            color: "blue",
            iconBg: "bg-blue-500/10 text-blue-400"
          },
          {
            id: "home",
            name: "Home & Lawn",
            blurb: "Walking pads, yard tools, backup power",
            icon: "fa-home",
            color: "emerald",
            iconBg: "bg-emerald-500/10 text-emerald-400"
          },
          {
            id: "tech",
            name: "Tech & Power",
            blurb: "Power stations, chargers, gadgets",
            icon: "fa-plug",
            color: "purple",
            iconBg: "bg-purple-500/10 text-purple-400"
          },
          {
            id: "vanlife",
            name: "Van Life & RV",
            blurb: "Portable power, camping, off-grid",
            icon: "fa-caravan",
            color: "amber",
            iconBg: "bg-amber-500/10 text-amber-400"
          }
        ];'''

new_cats = '''        const CATEGORIES = [
          {
            id: "tools",
            name: "Tools & DIY",
            blurb: "Drills, impacts, bits, jobsite bags",
            icon: "fa-tools",
            color: "orange",
            iconBg: "bg-orange-500/10 text-orange-400"
          },
          {
            id: "gig",
            name: "Gig & Delivery",
            blurb: "Car mounts, dash cams, driver power",
            icon: "fa-truck",
            color: "blue",
            iconBg: "bg-blue-500/10 text-blue-400"
          },
          {
            id: "home",
            name: "Home & Lawn",
            blurb: "Cleaning, fitness, yard & home backup",
            icon: "fa-home",
            color: "emerald",
            iconBg: "bg-emerald-500/10 text-emerald-400"
          },
          {
            id: "tech",
            name: "Tech & Power",
            blurb: "Power banks, wall chargers, laptop juice",
            icon: "fa-plug",
            color: "purple",
            iconBg: "bg-purple-500/10 text-purple-400"
          },
          {
            id: "vanlife",
            name: "Van Life & RV",
            blurb: "Solar, stations, camping & cargo",
            icon: "fa-caravan",
            color: "amber",
            iconBg: "bg-amber-500/10 text-amber-400"
          }
        ];'''

if old_cats not in text:
    raise SystemExit("CATEGORIES block not found")
text = text.replace(old_cats, new_cats, 1)

start = text.find("        // ── Product catalog")
end = text.find("        let activeCategory = null;")
if start < 0 or end < 0:
    raise SystemExit("catalog markers not found")

new_catalog = r'''        // ── Product catalog ─────────────────────────────────────────────
        // Rule: each product lives in ONE primary category only (no cross-posting).
        // featured: show in top "What's Selling" grid
        const PRODUCT_CATALOG = [
          // ── Tools & DIY ──────────────────────────────────────────────
          {
            asin: "B00IJ0ALYS",
            name: "DEWALT 20V MAX Drill & Impact Combo",
            sub: "DCK240C2 · 2 batteries + charger + bag",
            price: 149.0,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/dewalt.jpg",
            blurb: "Amazon's Choice jobsite kit — 10K+ bought/mo. The go-to cordless pair for DIY and pro handymen.",
            score: "9.6",
            categories: ["tools"],
            featured: true,
            compare: { amazon: 149.0, walmart: 159.0, ebay: 135.0 }
          },
          {
            asin: "B07K2KN7D7",
            name: "CRAFTSMAN V20 Drill & Impact Set",
            sub: "2 batteries · charger · bag · LED lights",
            price: 99.0,
            list: 169.0,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/craftsman.jpg",
            blurb: "Budget-friendly first cordless set that still feels pro. Strong starter kit for home DIY and light jobs.",
            score: "8.8",
            categories: ["tools"],
            featured: true,
            compare: { amazon: 99.0, walmart: 109.0, ebay: 89.0 }
          },
          {
            asin: "B00GMXFK3G",
            name: "DEWALT FlexTorq 40-Piece Bit Set",
            sub: "Impact Ready · storage case",
            price: 21.57,
            list: null,
            badge: "ADD-ON",
            badgeClass: "bg-slate-600",
            img: "images/dewalt.jpg",
            blurb: "Impact-ready bits that sell with every driver kit. High attach-rate consumable for tool owners.",
            score: "9.0",
            categories: ["tools"],
            featured: false,
            compare: { amazon: 21.57, walmart: 24.99, ebay: 19.0 }
          },
          {
            asin: "B07DH55YRX",
            name: "DEWALT 14-Piece Drill Bit Set",
            sub: "3-flats shank · wood / metal / plastic",
            price: 14.79,
            list: null,
            badge: "ADD-ON",
            badgeClass: "bg-slate-600",
            img: "images/craftsman.jpg",
            blurb: "Everyday drill bits for wood, metal, and plastic. Cheap, useful impulse add-on next to any drill kit.",
            score: "8.7",
            categories: ["tools"],
            featured: false,
            compare: { amazon: 14.79, walmart: 16.99, ebay: 12.5 }
          },
          {
            asin: "B0BPLMF8KC",
            name: "EWORK 3/4\" Cordless Impact Wrench",
            sub: "1500 ft-lbs · brushless · truck / tire work",
            price: 149.0,
            list: 229.99,
            badge: "HOT DEAL",
            badgeClass: "bg-amber-500",
            img: "images/dewalt.jpg",
            blurb: "High-torque impact for lug nuts, trailer work, and heavy DIY. Strong deal-price conversion.",
            score: "8.8",
            categories: ["tools"],
            featured: false,
            compare: { amazon: 149.0, walmart: 169.0, ebay: 135.0 }
          },
          {
            asin: "B0DQ5BCVL4",
            name: "1/2\" Cordless Impact Wrench (20V-style)",
            sub: "1700 ft-lbs · 4 modes · bare tool",
            price: 101.13,
            list: 139.99,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/craftsman.jpg",
            blurb: "Rising bare-tool impact for auto work and garage DIY. Great for buyers already on a battery platform.",
            score: "8.6",
            categories: ["tools"],
            featured: false,
            compare: { amazon: 101.13, walmart: 115.0, ebay: 95.0 }
          },
          {
            asin: "B07G9X19G1",
            name: "Coquimbo Rechargeable LED Work Light",
            sub: "2-pack · magnetic base · 360° · USB-C",
            price: 11.89,
            list: 13.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/work-light.jpg",
            blurb: "#1 job-site lighting pick. Magnetic mechanic lights for under-hood work and dark job boxes.",
            score: "9.0",
            categories: ["tools"],
            featured: true,
            compare: { amazon: 11.89, walmart: 14.99, ebay: 10.5 }
          },
          {
            asin: "B09ZJYWNWR",
            name: "DEWALT TSTAK 16\" Tool Bag",
            sub: "Hard bottom · waterproof base · 1680D",
            price: 48.98,
            list: null,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/tool-bag.jpg",
            blurb: "Amazon's Choice tote for drills and bits. Stacks with TSTAK and keeps a jobsite kit organized.",
            score: "9.1",
            categories: ["tools"],
            featured: true,
            compare: { amazon: 48.98, walmart: 54.99, ebay: 44.0 }
          },

          // ── Gig & Delivery ───────────────────────────────────────────
          {
            asin: "B0DN1S1YLV",
            name: "ANDERY MagSafe Car Phone Mount",
            sub: "78+ lb suction · 2400gf magnets · 360°",
            price: 26.99,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/phone-mount.jpg",
            blurb: "#1 car cradle bestseller. One-hand MagSafe dock for delivery apps and navigation every stop.",
            score: "9.3",
            categories: ["gig"],
            featured: true,
            compare: { amazon: 26.99, walmart: 29.99, ebay: 24.0 }
          },
          {
            asin: "B09VPHVT2Z",
            name: "Anker 737 Power Bank (PowerCore 24K)",
            sub: "140W · 24,000mAh · flight-safe",
            price: 109.99,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/anker.jpg",
            blurb: "All-day phone + tablet power for multi-app drivers. Laptop-class output when you need a full shift charge.",
            score: "9.3",
            categories: ["gig"],
            featured: true,
            compare: { amazon: 109.99, walmart: 119.99, ebay: 95.0 }
          },
          {
            asin: "B0FDWMP57L",
            name: "OlarHike Portable Tire Inflator",
            sub: "6000mAh cordless + 12V · auto shut-off",
            price: 29.99,
            list: 34.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/tire-inflator.jpg",
            blurb: "#1 portable compressor. 10K+ bought/mo — roadside top-offs without hunting a gas station.",
            score: "9.4",
            categories: ["gig"],
            featured: true,
            compare: { amazon: 29.99, walmart: 32.99, ebay: 27.0 }
          },
          {
            asin: "B00BYH6C1E",
            name: "Drop Stop Car Seat Gap Filler (2-Pack)",
            sub: "Shark Tank original · LED + slide pad",
            price: 24.99,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/gap-filler.jpg",
            blurb: "#1 seat gap filler. Stops phones and keys vanishing between console and seat on long routes.",
            score: "9.2",
            categories: ["gig"],
            featured: true,
            compare: { amazon: 24.99, walmart: 27.99, ebay: 22.0 }
          },
          {
            asin: "B0C6YBHKJ5",
            name: "REDTIGER F7N Touch 4K Dash Cam",
            sub: "Front + rear · 128GB · WiFi · GPS",
            price: 139.99,
            list: 169.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/dashcam.jpg",
            blurb: "Amazon's Choice dual dash cam. 9K+ bought/mo — proof for insurance, rideshare, and delivery fleets.",
            score: "9.1",
            categories: ["gig"],
            featured: true,
            compare: { amazon: 139.99, walmart: 149.99, ebay: 125.0 }
          },
          {
            asin: "B004MDXS0U",
            name: "BESTEK 300W Car Power Inverter",
            sub: "12V → 110V · dual USB · 2 AC outlets",
            price: 26.99,
            list: 34.99,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/inverter.jpg",
            blurb: "Plug-in AC + USB for laptops and chargers on the road. Classic driver essential at a low ticket.",
            score: "9.0",
            categories: ["gig"],
            featured: false,
            compare: { amazon: 26.99, walmart: 29.99, ebay: 24.0 }
          },

          // ── Home & Lawn ──────────────────────────────────────────────
          {
            asin: "B0G51V78YK",
            name: "Walking Pad with Incline & Handle Bar",
            sub: "2026 Upgrade · 0.6–7.6 MPH · 350 lb",
            price: 99.99,
            list: 139.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/walkingpad.jpg",
            blurb: "TikTok-viral under-desk treadmill. Quiet home fitness that folds away after work.",
            score: "9.4",
            categories: ["home"],
            featured: true,
            compare: { amazon: 99.99, walmart: 109.99, ebay: 89.0 }
          },
          {
            asin: "B07R295MLS",
            name: "eufy Robot Vacuum 11S MAX",
            sub: "2000Pa · super-thin · self-charging",
            price: 149.99,
            list: 279.99,
            badge: "HOT DEAL",
            badgeClass: "bg-amber-500",
            img: "images/eufy-vac.jpg",
            blurb: "Amazon's Choice robovac with deep list discount. Quiet daily cleaner for floors and pet hair.",
            score: "9.1",
            categories: ["home"],
            featured: true,
            compare: { amazon: 149.99, walmart: 159.99, ebay: 135.0 }
          },
          {
            asin: "B0BVGSX46M",
            name: "Westinghouse ePX3500 Pressure Washer",
            sub: "2500 max PSI · 1.76 GPM · 5 nozzles",
            price: 169.0,
            list: 199.0,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/pressure-washer.jpg",
            blurb: "10K+ bought/mo compact electric washer for driveways, decks, siding, and cars at home.",
            score: "9.3",
            categories: ["home"],
            featured: true,
            compare: { amazon: 169.0, walmart: 179.0, ebay: 155.0 }
          },
          {
            asin: "B0947XLWFW",
            name: "Saker Mini Chainsaw (Cordless)",
            sub: "4-inch · pruning & yard cleanup",
            price: 39.98,
            list: 51.95,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/minichainsaw.jpg",
            blurb: "Social DIY favorite for branches and storm cleanup. Compact cordless saw for home yards.",
            score: "8.9",
            categories: ["home"],
            featured: true,
            compare: { amazon: 39.98, walmart: 44.99, ebay: 36.0 }
          },
          {
            asin: "B0GY4TQ2P8",
            name: "Anker SOLIX S2000 Power Station",
            sub: "2010Wh · 1500W · home backup",
            price: 599.99,
            list: 1199.0,
            badge: "FORECAST",
            badgeClass: "bg-violet-500",
            img: "images/anker-solix.jpg",
            blurb: "Whole-home adjacent backup for outages and storm season. Bigger capacity without a generator.",
            score: "9.1",
            categories: ["home"],
            featured: true,
            compare: { amazon: 599.99, walmart: 649.0, ebay: 575.0 }
          },
          {
            asin: "B0DFG2WDQH",
            name: "Jackery Explorer 2000 v2 Power Station",
            sub: "2042Wh · 2200W · emergency / blackouts",
            price: 999.0,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/jackery.jpg",
            blurb: "Bestselling 2kWh class station for longer home outages and fridge + essentials backup.",
            score: "9.2",
            categories: ["home"],
            featured: false,
            compare: { amazon: 999.0, walmart: 1049.0, ebay: 920.0 }
          },

          // ── Tech & Power ─────────────────────────────────────────────
          {
            asin: "B0FHPMX7DR",
            name: "EF ECOFLOW 25,000mAh 170W Power Bank",
            sub: "Dual 140W USB-C · smart display",
            price: 62.99,
            list: 129.99,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/ecoflow-pb.jpg",
            blurb: "Deep-discount laptop power bank. Dual high-watt USB-C for phones and notebooks on the go.",
            score: "9.0",
            categories: ["tech"],
            featured: true,
            compare: { amazon: 62.99, walmart: 69.99, ebay: 58.0 }
          },
          {
            asin: "B0F66LNB8D",
            name: "Anker Prime 26,250mAh Power Bank",
            sub: "300W max · app control · TSA-friendly",
            price: 179.99,
            list: null,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/anker.jpg",
            blurb: "Flagship Anker bank for MacBooks and multi-device desks. High-watt next-gen charging.",
            score: "9.1",
            categories: ["tech"],
            featured: false,
            compare: { amazon: 179.99, walmart: 189.99, ebay: 165.0 }
          },
          {
            asin: "B0GXX52D5Y",
            name: "Belkin 25K 158W Portable Charger",
            sub: "Integrated USB-C · laptop + phone",
            price: 84.99,
            list: 99.99,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/ecoflow-pb.jpg",
            blurb: "Built-in cable convenience from a trusted brand. Laptop-class juice without carrying a brick.",
            score: "8.9",
            categories: ["tech"],
            featured: false,
            compare: { amazon: 84.99, walmart: 89.99, ebay: 78.0 }
          },
          {
            asin: "B0H1B4V2WL",
            name: "Solar Power Bank 20,000mAh (4 panels)",
            sub: "Built-in cables · emergency charging",
            price: 39.99,
            list: 49.99,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/anker.jpg",
            blurb: "Impulse solar bank for emergency kits and outdoor days. Strong visual product for tech gifts.",
            score: "8.4",
            categories: ["tech"],
            featured: false,
            compare: { amazon: 39.99, walmart: 44.99, ebay: 35.0 }
          },
          {
            asin: "B0D7PPG25F",
            name: "Jackery Explorer 1000 v2 Power Station",
            sub: "1070Wh LiFePO4 · 1500W · 1-hr charge",
            price: 429.0,
            list: 799.0,
            badge: "HOT DEAL",
            badgeClass: "bg-amber-500",
            img: "images/jackery.jpg",
            blurb: "10K+ bought/mo portable power station. The best-known mid-size unit for multi-device off-grid power.",
            score: "9.5",
            categories: ["tech"],
            featured: true,
            compare: { amazon: 429.0, walmart: 449.0, ebay: 399.0 }
          },

          // ── Van Life & RV ────────────────────────────────────────────
          {
            asin: "B0FR555DVH",
            name: "Jackery Explorer 500 v2 Power Station",
            sub: "512Wh · 500W · compact travel",
            price: 319.0,
            list: 449.0,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/jackery.jpg",
            blurb: "Entry van / car-camping station without the 1000-class price. Weekend trips and small fridge loads.",
            score: "8.9",
            categories: ["vanlife"],
            featured: true,
            compare: { amazon: 319.0, walmart: 339.0, ebay: 295.0 }
          },
          {
            asin: "B0GKRTX336",
            name: "BLUETTI Elite 300 Power Station",
            sub: "3014Wh · 2400W · RV TT-30 port",
            price: 1098.99,
            list: 1449.0,
            badge: "FORECAST",
            badgeClass: "bg-violet-500",
            img: "images/bluetti.jpg",
            blurb: "RV-ready high-capacity station with TT-30. Premium ticket for serious van builds and boondocking.",
            score: "9.0",
            categories: ["vanlife"],
            featured: false,
            compare: { amazon: 1098.99, walmart: 1149.0, ebay: 999.0 }
          },
          {
            asin: "B0FX8P4JST",
            name: "Jackery SolarSaga 100W Air Panel",
            sub: "Bifacial · 7 lb · IP65 · foldable",
            price: 299.0,
            list: null,
            badge: "FORECAST",
            badgeClass: "bg-violet-500",
            img: "images/jackery-solar.jpg",
            blurb: "Lightweight Jackery-compatible solar for Explorer stations. Core attach-rate upsell for van kits.",
            score: "9.0",
            categories: ["vanlife"],
            featured: true,
            compare: { amazon: 299.0, walmart: 319.0, ebay: 279.0 }
          },
          {
            asin: "B09BC9CS49",
            name: "Amiss Stretchable Trunk Cargo Net",
            sub: "35.4×15.8\" · hooks · SUV / van / truck",
            price: 9.99,
            list: null,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/cargo-net.jpg",
            blurb: "Cheap cargo organizer that keeps bins, bags, and gear from sliding in a van or SUV cargo bay.",
            score: "8.7",
            categories: ["vanlife"],
            featured: false,
            compare: { amazon: 9.99, walmart: 11.99, ebay: 8.5 }
          },
          {
            asin: "B00339C3P0",
            name: "Coleman Portable Camping Chair",
            sub: "4-can cooler pouch · 325 lb · carry bag",
            price: 34.99,
            list: 53.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/camp-chair.jpg",
            blurb: "Bestselling camp chair with built-in cooler. Van life, trailheads, and fireside essentials.",
            score: "9.2",
            categories: ["vanlife"],
            featured: true,
            compare: { amazon: 34.99, walmart: 39.99, ebay: 32.0 }
          }
        ];

'''

text = text[:start] + new_catalog + text[end:]
path.write_text(text, encoding="utf-8")
print("OK: catalog reorganized")

# quick sanity: count categories
import re
cats = re.findall(r'categories:\s*\["([^"]+)"\]', text)
from collections import Counter
print("Category counts:", dict(Counter(cats)))
print("Total single-cat products:", len(cats))
