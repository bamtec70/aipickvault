# -*- coding: utf-8 -*-
"""Populate all categories with curated fast-sellers + filter UI."""
from pathlib import Path

p = Path(r"C:\Users\bamte\aipickvault\index.html")
html = p.read_text(encoding="utf-8")

# ── Replace categories section ─────────────────────────────────────────────
cat_start = html.find("    <!-- Categories Section -->")
cat_end = html.find("    <!-- Videos / TikTok Section -->")
if cat_start < 0 or cat_end < 0:
    raise SystemExit("category markers missing")

new_cats = r"""    <!-- Categories Section -->
    <div id="categories" class="bg-slate-900 py-16 border-y border-slate-800">
        <div class="max-w-7xl mx-auto px-6">
            <div class="text-center mb-10">
                <div class="uppercase tracking-[2px] text-xs font-semibold text-sky-400 mb-1">EXPLORE BY NEED</div>
                <h2 class="section-header">Shop by Category</h2>
                <p class="text-slate-400 mt-2 text-sm max-w-xl mx-auto">Tap a category to see curated picks that move fast for hustlers, DIYers, and on-the-road pros.</p>
            </div>
            
            <div id="category-nav" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <!-- filled by script -->
            </div>

            <div class="mt-12">
                <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
                    <div>
                        <div class="uppercase tracking-[2px] text-xs font-semibold text-sky-400 mb-1">CATEGORY PICKS</div>
                        <h3 id="category-title" class="text-2xl font-bold tracking-tight">All categories</h3>
                        <p id="category-sub" class="text-sm text-slate-400 mt-1">Showing every curated product across the vault.</p>
                    </div>
                    <button type="button" id="clear-category-filter" class="hidden px-4 py-2 text-sm border border-slate-700 rounded-2xl hover:bg-slate-800">
                        Show all
                    </button>
                </div>
                <div id="category-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    <!-- filled by script -->
                </div>
            </div>
        </div>
    </div>

"""
html = html[:cat_start] + new_cats + html[cat_end:]

# ── Replace product catalog + render logic ────────────────────────────────
# Find and replace from PRODUCT_CATALOG through end of renderProducts function
start = html.find("        // ── Product catalog")
if start < 0:
    start = html.find("        const PRODUCT_CATALOG = [")
end = html.find("        function applyAmazonTags()")
if start < 0 or end < 0:
    raise SystemExit(f"catalog markers missing {start} {end}")

new_js = r"""
        // ── Categories ───────────────────────────────────────────────────
        const CATEGORIES = [
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
        ];

        // ── Product catalog (hot / rising — multi-category) ──────────────
        // categories: which shop-by-need buckets this product fills
        // featured: show in top "What's Selling" grid
        const PRODUCT_CATALOG = [
          {
            asin: "B0G51V78YK",
            name: "Walking Pad with Incline & Handle Bar",
            sub: "2026 Upgrade · 0.6–7.6 MPH · 350 lb",
            price: 99.99,
            list: 139.99,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/walkingpad.jpg",
            blurb: "TikTok-viral under-desk walking pad. 7K+ bought last month. Drivers and remote hustlers stack steps while working.",
            score: "9.4",
            categories: ["home", "gig"],
            featured: true,
            compare: { amazon: 99.99, walmart: 109.99, ebay: 89.0 }
          },
          {
            asin: "B00IJ0ALYS",
            name: "DEWALT 20V MAX Drill & Impact Combo",
            sub: "DCK240C2 · 2 batteries + charger + bag",
            price: 149.0,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/dewalt.jpg",
            blurb: "Amazon's Choice, 10K+ bought/mo, 60K+ reviews. The #1 jobsite kit for gig techs and handymen.",
            score: "9.6",
            categories: ["tools", "gig"],
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
            blurb: "Budget tool kit that still converts. Perfect first set for side hustles and secondary crews.",
            score: "8.8",
            categories: ["tools", "gig"],
            featured: true,
            compare: { amazon: 99.0, walmart: 109.0, ebay: 89.0 }
          },
          {
            asin: "B0947XLWFW",
            name: "Saker Mini Chainsaw (Cordless)",
            sub: "4-inch · 20V · pruning & yard work",
            price: 39.98,
            list: 51.95,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/minichainsaw.jpg",
            blurb: "Amazon's Choice mini saw — social DIY favorite for branches, storm cleanup, and gift season.",
            score: "8.9",
            categories: ["tools", "home"],
            featured: true,
            compare: { amazon: 39.98, walmart: 44.99, ebay: 36.0 }
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
            blurb: "High-attach rate accessory with DEWALT kits. Impulse add-to-cart for anyone who already owns a 20V driver.",
            score: "9.0",
            categories: ["tools", "gig"],
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
            blurb: "Everyday consumable that sells with every drill kit. Cheap, useful, high conversion.",
            score: "8.7",
            categories: ["tools"],
            featured: false,
            compare: { amazon: 14.79, walmart: 16.99, ebay: 12.5 }
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
            blurb: "Laptop-class power bank for delivery drivers, travelers, and multi-device days. 2K+ bought last month.",
            score: "9.3",
            categories: ["gig", "tech", "vanlife"],
            featured: true,
            compare: { amazon: 109.99, walmart: 119.99, ebay: 95.0 }
          },
          {
            asin: "B0FHPMX7DR",
            name: "EF ECOFLOW 25,000mAh 170W Power Bank",
            sub: "Dual 140W USB-C · smart display",
            price: 62.99,
            list: 129.99,
            badge: "RISING",
            badgeClass: "bg-emerald-500",
            img: "images/ecoflow-pb.jpg",
            blurb: "Rising laptop power bank with deep discount. Dual high-watt USB-C for phones + laptops on the road.",
            score: "9.0",
            categories: ["gig", "tech", "vanlife"],
            featured: true,
            compare: { amazon: 62.99, walmart: 69.99, ebay: 58.0 }
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
            blurb: "10K+ bought/mo. Van life, blackouts, and jobsite backup in a portable 23.8 lb pack.",
            score: "9.5",
            categories: ["tech", "vanlife", "home", "gig"],
            featured: true,
            compare: { amazon: 429.0, walmart: 449.0, ebay: 399.0 }
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
            blurb: "#1 New Release class. Bigger home-backup and RV demand climbing into storm season.",
            score: "9.1",
            categories: ["tech", "vanlife", "home"],
            featured: true,
            compare: { amazon: 599.99, walmart: 649.0, ebay: 575.0 }
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
            blurb: "Higher-capacity RV / whole-home adjacent backup. Premium ticket for serious off-grid and outage buyers.",
            score: "9.0",
            categories: ["tech", "vanlife", "home"],
            featured: false,
            compare: { amazon: 1098.99, walmart: 1149.0, ebay: 999.0 }
          },
          {
            asin: "B0DFG2WDQH",
            name: "Jackery Explorer 2000 v2 Power Station",
            sub: "2042Wh · 2200W · camping / emergency",
            price: 999.0,
            list: null,
            badge: "HOT NOW",
            badgeClass: "bg-rose-500",
            img: "images/jackery.jpg",
            blurb: "Bestselling 2kWh class station for longer outages and full RV weekends. Strong upgrade path from the 1000 v2.",
            score: "9.2",
            categories: ["vanlife", "tech", "home"],
            featured: false,
            compare: { amazon: 999.0, walmart: 1049.0, ebay: 920.0 }
          },
          {
            asin: "B0FR555DVH",
            name: "Jackery Explorer 500 v2 Power Station",
            sub: "512Wh · 500W · compact travel",
            price: 319.0,
            list: 449.0,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/jackery.jpg",
            blurb: "Entry solar-generator size that converts for weekend camping and car camping without the 1000-class price.",
            score: "8.9",
            categories: ["vanlife", "tech", "gig"],
            featured: false,
            compare: { amazon: 319.0, walmart: 339.0, ebay: 295.0 }
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
            blurb: "Next-gen Anker flagship power bank. Higher wattage for newer MacBooks and multi-device charging setups.",
            score: "9.1",
            categories: ["tech", "gig", "vanlife"],
            featured: false,
            compare: { amazon: 179.99, walmart: 189.99, ebay: 165.0 }
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
            blurb: "High-torque impact for tire shops, mobile mechanics, and heavy DIY. Strong limited-time deal conversion.",
            score: "8.8",
            categories: ["tools", "gig"],
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
            blurb: "Rising mobile-mechanic pick for lug nuts and auto work. Bare-tool buyers already on a battery platform.",
            score: "8.6",
            categories: ["tools", "gig"],
            featured: false,
            compare: { amazon: 101.13, walmart: 115.0, ebay: 95.0 }
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
            blurb: "Built-in cable convenience for travelers. Strong brand trust and laptop-class output without a brick.",
            score: "8.9",
            categories: ["tech", "gig"],
            featured: false,
            compare: { amazon: 84.99, walmart: 89.99, ebay: 78.0 }
          },
          {
            asin: "B0H1B4V2WL",
            name: "Solar Power Bank 20,000mAh (4 panels)",
            sub: "Built-in cables · emergency / outdoor",
            price: 39.99,
            list: 49.99,
            badge: "VALUE",
            badgeClass: "bg-sky-500",
            img: "images/anker.jpg",
            blurb: "Impulse outdoor / emergency charger. Solar storytelling works great on TikTok for van and camping content.",
            score: "8.4",
            categories: ["vanlife", "home", "tech"],
            featured: false,
            compare: { amazon: 39.99, walmart: 44.99, ebay: 35.0 }
          }
        ];

        let activeCategory = null;

        function money(n) {
          const x = Number(n);
          return "$" + (x % 1 ? x.toFixed(2) : String(x));
        }

        function productCardHTML(p) {
          const off = p.list ? Math.round((1 - p.price / p.list) * 100) : 0;
          const priceBlock = p.list
            ? '<span class="text-3xl font-semibold">' + money(p.price) + '</span>' +
              '<span class="text-sm line-through text-slate-500">' + money(p.list) + '</span>' +
              '<span class="text-emerald-400 text-sm font-medium">' + off + '% off</span>'
            : '<span class="text-3xl font-semibold">' + money(p.price) + '</span>';
          const cats = (p.categories || []).map(function (c) {
            return '<span class="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">' + c + '</span>';
          }).join(" ");
          return (
            '<div class="product-card bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden" data-asin="' + p.asin + '" data-compare=\'' + JSON.stringify(p.compare) + '\'>' +
              '<div class="relative bg-white">' +
                '<img src="' + p.img + '" alt="' + p.name.replace(/"/g, "") + '" class="w-full h-48 object-contain p-4" loading="lazy">' +
                '<div class="absolute top-4 left-4"><span class="' + p.badgeClass + ' text-white text-xs px-2.5 py-1 rounded-full font-semibold">' + p.badge + '</span></div>' +
                '<div class="absolute top-4 right-4 bg-black/70 px-3 py-1 rounded-2xl text-xs flex items-center gap-x-1">' +
                  '<i class="fa-solid fa-robot text-sky-400"></i><span class="font-mono text-[10px] text-white">GROK</span></div>' +
              '</div>' +
              '<div class="p-5">' +
                '<div class="flex flex-wrap gap-1.5 mb-2">' + cats + '</div>' +
                '<h3 class="font-semibold text-xl leading-tight">' + p.name + '</h3>' +
                '<p class="text-sm text-slate-400 mt-0.5">' + p.sub + '</p>' +
                '<div class="flex items-baseline gap-x-2 mb-4 mt-3 flex-wrap gap-y-1">' + priceBlock + '</div>' +
                '<p class="text-sm text-slate-300 mb-5 line-clamp-3">' + p.blurb + ' <span class="text-sky-400">Grok score: ' + p.score + '/10</span></p>' +
                '<div class="flex gap-3">' +
                  '<a href="https://www.amazon.com/dp/' + p.asin + '" data-asin="' + p.asin + '" data-affiliate="amazon" target="_blank" rel="nofollow sponsored noopener" ' +
                    'class="flex-1 bg-white hover:bg-slate-100 transition-colors text-slate-950 text-center font-semibold py-3 rounded-2xl text-sm">Shop on Amazon</a>' +
                  '<button type="button" onclick="compareProduct(this)" class="px-5 border border-slate-700 hover:bg-slate-800 rounded-2xl text-sm font-medium">Compare</button>' +
                '</div>' +
                '<div class="mt-4 text-[10px] text-slate-500 flex items-center gap-x-1">' +
                  '<i class="fa-solid fa-info-circle"></i>' +
                  '<span>As an Amazon Associate I earn from qualifying purchases.</span></div>' +
              '</div></div>'
          );
        }

        function productsForCategory(catId) {
          if (!catId) return PRODUCT_CATALOG.slice();
          return PRODUCT_CATALOG.filter(function (p) {
            return (p.categories || []).indexOf(catId) >= 0;
          });
        }

        function renderFeatured() {
          const grid = document.getElementById("product-grid");
          if (!grid) return;
          const list = PRODUCT_CATALOG.filter(function (p) { return p.featured; });
          grid.innerHTML = list.map(productCardHTML).join("");
        }

        function renderCategoryNav() {
          const nav = document.getElementById("category-nav");
          if (!nav) return;
          nav.innerHTML = CATEGORIES.map(function (c) {
            const count = productsForCategory(c.id).length;
            const active = activeCategory === c.id;
            const ring = active ? " ring-2 ring-sky-400 border-sky-500" : " border-slate-800";
            return (
              '<button type="button" data-cat="' + c.id + '" class="category-btn group bg-slate-950 hover:bg-slate-800' + ring + ' rounded-3xl p-6 flex flex-col items-center text-center transition-all w-full">' +
                '<div class="w-14 h-14 ' + c.iconBg + ' rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">' +
                  '<i class="fa-solid ' + c.icon + ' text-3xl"></i></div>' +
                '<div class="font-semibold">' + c.name + '</div>' +
                '<div class="text-xs text-slate-400 mt-1">' + c.blurb + '</div>' +
                '<div class="mt-3 text-xs font-medium text-sky-400">' + count + ' picks</div>' +
              '</button>'
            );
          }).join("");

          nav.querySelectorAll(".category-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
              const id = btn.getAttribute("data-cat");
              if (activeCategory === id) {
                setCategory(null);
              } else {
                setCategory(id);
              }
            });
          });
        }

        function renderCategoryProducts() {
          const grid = document.getElementById("category-grid");
          const title = document.getElementById("category-title");
          const sub = document.getElementById("category-sub");
          const clearBtn = document.getElementById("clear-category-filter");
          if (!grid) return;

          const list = productsForCategory(activeCategory);
          grid.innerHTML = list.length
            ? list.map(productCardHTML).join("")
            : '<p class="text-slate-400 col-span-full text-center py-10">No products in this category yet.</p>';

          if (activeCategory) {
            const c = CATEGORIES.find(function (x) { return x.id === activeCategory; });
            if (title) title.textContent = c ? c.name : activeCategory;
            if (sub) sub.textContent = (c ? c.blurb + " · " : "") + list.length + " curated products that move fast.";
            if (clearBtn) clearBtn.classList.remove("hidden");
          } else {
            if (title) title.textContent = "All categories";
            if (sub) sub.textContent = "Showing every curated product across the vault (" + list.length + ").";
            if (clearBtn) clearBtn.classList.add("hidden");
          }

          applyAmazonTags();
        }

        function setCategory(id) {
          activeCategory = id;
          renderCategoryNav();
          renderCategoryProducts();
          if (id) {
            const el = document.getElementById("category-grid");
            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }

        function renderProducts() {
          renderFeatured();
          renderCategoryNav();
          renderCategoryProducts();
          const clearBtn = document.getElementById("clear-category-filter");
          if (clearBtn) {
            clearBtn.addEventListener("click", function () { setCategory(null); });
          }
          // deep-link ?cat=tools
          try {
            const q = new URLSearchParams(window.location.search).get("cat");
            if (q && CATEGORIES.some(function (c) { return c.id === q; })) {
              setCategory(q);
            }
          } catch (e) {}
        }

"""

html = html[:start] + new_js + "\n" + html[end:]

# Update category subtext in older static text if any left
html = html.replace(
    'Last updated: <time id="last-updated" datetime="2026-07-12">July 12, 2026</time>',
    'Last updated: <time id="last-updated" datetime="2026-07-12">July 12, 2026 · Categories filled</time>',
)

p.write_text(html, encoding="utf-8")
print("OK", len(html), "products", html.count('asin:'))
