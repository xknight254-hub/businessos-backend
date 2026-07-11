# BusinessOS — Icon Audit

## Methodology
Audited all 31 Dart source files across the Flutter mobile app.
Counted every icon usage: LucideIcons, Material Icons (Icons.*), and emoji characters.

## Summary

| Category | Count |
|---|---|
| **LucideIcons references** | ~140 across 22 files |
| **Material Icons (Icons.*)** | ~40 across 24 files |
| **Emoji characters** | 3 (📷, 🖼️) |
| **Files using only LucideIcons** | 14 |
| **Files mixing Lucide + Material** | 10 |
| **Files using only Material** | 7 (mostly widgets) |

## Detailed Audit

### Screens using LucideIcons (primary icon set) ✅
| File | Lucide | Material | Notes |
|---|---|---|---|
| `morning_briefing_screen.dart` | 7 | 0 | Clean Lucide usage |
| `pos_screen.dart` | 6 | 0 | Clean Lucide usage |
| `inventory_screen.dart` | 3 | 0 | Clean Lucide usage (qr_code_scanner → LucideIcons.scanLine) |
| `more_screen.dart` | 11 | 0 | Clean Lucide usage |
| `customers_screen.dart` | 4 | 0 | Clean Lucide usage |
| `customer_detail_screen.dart` | 6 | 0 | Clean Lucide usage |
| `reports_screen.dart` | 10 | 0 | Clean Lucide usage |
| `daily_summary_screen.dart` | 4 | 0 | Clean Lucide usage |
| `notifications_screen.dart` | 5 | 0 | Clean Lucide usage |
| `memory_screen.dart` | 5 | 0 | Clean Lucide usage |
| `ai_partner_screen.dart` | 3 | 1 | 1 emoji (📤 send icon) |
| `search_screen.dart` | 7 | 0 | Clean Lucide usage |
| `payments_screen.dart` | 5 | 0 | Clean Lucide usage |
| `etims_screen.dart` | 6 | 0 | Clean Lucide usage |
| `purchase_order_screen.dart` | 1 | 0 | Clean Lucide usage |
| `suppliers_screen.dart` | 2 | 0 | Clean Lucide usage |
| `security_screen.dart` | 4 | 0 | Clean Lucide usage |
| `auth_screen.dart` | 1 | 0 | Clean Lucide usage |
| `product_creation_screen.dart` | 1 | 1 | Uses Icons.qr_code (→ LucideIcons.scanLine) |
| `product_detail_screen.dart` | 3 | 0 | Clean Lucide usage |
| `stock_count_screen.dart` | 1 | 1 | Uses Icons.qr_code_scanner (→ LucideIcons.scanLine) |

### Widgets using Material Icons (need migration)
| File | Lucide | Material | Emoji | Notes |
|---|---|---|---|---|
| `main.dart` | 0 | 8 | 0 | Bottom nav uses Icons.home, shopping_cart, etc. → LucideIcons |
| `mpesa_payment_sheet.dart` | 0 | 3 | 0 | Has AppColors.safaricomGreen constant |
| `barcode_scanner.dart` | 0 | 5 | 1 | Uses Icons.close, flash_on, keyboard, qr_code_scanner |
| `pin_entry.dart` | 0 | 1 | 0 | Uses Icons.backspace_outlined |
| `daily_report_card.dart` | 0 | 1 | 0 | Uses Icons.arrow_upward |
| `ai_insight_card.dart` | 0 | 1 | 0 | Uses Icons.arrow_forward |
| `states.dart` | 0 | 4 | 0 | Uses Icons.add, cloud_off, refresh, sync |
| `voice_input.dart` | 0 | 1 | 0 | Uses Icons.mic, hourglass_top |
| `buttons.dart` | 0 | 1 | 0 | Uses Icons.add |
| `misc_widgets.dart` | 0 | 3 | 0 | Uses Icons.search, mic, refresh |

### Emoji usage (needs replacement)
| File | Emoji | Context |
|---|---|---|
| `barcode_scanner.dart` | 📷 | Camera placeholder → LucideIcons.camera |
| `stock_count_screen.dart` | 📷 | Camera placeholder → LucideIcons.camera |
| `ai_partner_screen.dart` | 📤 | Send button → LucideIcons.send |

## Key Findings

1. **Lucide_icons package is already installed** — just not consistently used
2. **main.dart bottom nav** uses Material Icons — these look identical to Lucide equivalents
3. **Widget files** (mpesa_payment_sheet.dart, barcode_scanner.dart, etc.) use Material Icons — need migration to Lucide
4. **3 emoji characters** used as icon placeholders — need replacement with Lucide equivalents
5. **AppColors.safaricomGreen** in mpesa_payment_sheet.dart — should use our design system tokens

## Replacement Recommendations

| Current Icon | Lucide Replacement | Files Affected |
|---|---|---|
| `Icons.home` | `LucideIcons.home` | main.dart |
| `Icons.home_outlined` | `LucideIcons.home` (outlined variant) | main.dart |
| `Icons.shopping_cart_outlined` | `LucideIcons.shoppingCart` | main.dart |
| `Icons.shopping_cart` | `LucideIcons.shoppingCart` | main.dart |
| `Icons.inventory_2_outlined` | `LucideIcons.package` | main.dart |
| `Icons.inventory_2` | `LucideIcons.package` | main.dart |
| `Icons.more_horiz` | `LucideIcons.moreHorizontal` | main.dart |
| `Icons.close` | `LucideIcons.x` | barcode_scanner.dart |
| `Icons.flash_on` | `LucideIcons.zap` | barcode_scanner.dart |
| `Icons.keyboard` | `LucideIcons.keyboard` | barcode_scanner.dart |
| `Icons.qr_code_scanner` | `LucideIcons.scanLine` | barcode_scanner.dart, stock_count_screen.dart |
| `Icons.backspace_outlined` | `LucideIcons.delete` | pin_entry.dart |
| `Icons.arrow_upward` | `LucideIcons.arrowUp` | daily_report_card.dart |
| `Icons.arrow_forward` | `LucideIcons.arrowRight` | ai_insight_card.dart |
| `Icons.add` | `LucideIcons.plus` | states.dart, buttons.dart |
| `Icons.cloud_off` | `LucideIcons.wifiOff` | states.dart |
| `Icons.refresh` | `LucideIcons.refreshCw` | states.dart, misc_widgets.dart |
| `Icons.sync` | `LucideIcons.refreshCw` | states.dart |
| `Icons.mic` | `LucideIcons.mic` | voice_input.dart, misc_widgets.dart |
| `Icons.hourglass_top` | `LucideIcons.hourglass` | voice_input.dart |
| `Icons.search` | `LucideIcons.search` | misc_widgets.dart |
| `Icons.smartphone` | `LucideIcons.smartphone` | mpesa_payment_sheet.dart, payments_screen.dart |
| `Icons.check_circle` | `LucideIcons.checkCircle` | mpesa_payment_sheet.dart, barcode_scanner.dart |
| `Icons.cancel` | `LucideIcons.xCircle` | mpesa_payment_sheet.dart |
| `📷` emoji | `LucideIcons.camera` | barcode_scanner.dart, stock_count_screen.dart |
| `📤` emoji | `LucideIcons.send` | ai_partner_screen.dart |
