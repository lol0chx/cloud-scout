import SwiftUI

// MARK: - Color tokens (from design handoff)

extension Color {
    // Surface
    static let csBg      = Color(hex: "eef0f3")
    static let csCard    = Color(hex: "ffffff")
    static let csBorder  = Color(hex: "e8eaee")
    static let csChip    = Color(hex: "f1f3f5")
    static let csText    = Color(hex: "0f172a")
    static let csSub     = Color(hex: "64748b")
    static let csFaint   = Color(hex: "94a3b8")

    // Semantic
    static let csNBA     = Color(hex: "2563eb")
    static let csMLB     = Color(hex: "d97706")
    static let csLive    = Color(hex: "ef4444")
    static let csWin     = Color(hex: "16a34a")
    static let csLoss    = Color(hex: "dc2626")

    // Dark palette (AI Scout)
    static let csDarkBg      = Color(hex: "0d0d0d")
    static let csDarkCard    = Color(hex: "1c1c2e")
    static let csDarkBorder  = Color(hex: "2a2a3e")
    static let csDarkPrimary = Color(hex: "5b8ff7")
    static let csDarkSub     = Color(hex: "8a8a9a")

    // MARK: Legacy aliases (keep existing views compiling)

    // Light feed aliases → surface/semantic tokens
    static let feedBg     = csBg
    static let feedCard   = csCard
    static let feedBorder = csBorder
    static let feedChip   = csChip
    static let feedText   = csText
    static let feedSub    = csSub
    static let feedNBA    = csNBA
    static let feedMLB    = csMLB
    static let feedLive   = csLive

    // Dark "app" aliases — used by the current dark-themed screens
    static let appBg      = csDarkBg
    static let appCard    = csDarkCard
    static let appBorder  = csDarkBorder
    static let appPrimary = csDarkPrimary
    static let appSub     = csDarkSub
    static let appWin     = Color(hex: "2ea44f")
    static let appLoss    = Color(hex: "cf222e")
    static let appMLB     = Color(hex: "f4c742")

    init(hex: String) {
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8)  & 0xFF) / 255
        let b = Double( int        & 0xFF) / 255
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1)
    }
}

// MARK: - Status pill palette

struct StatusPillPalette {
    let background: Color
    let foreground: Color

    static let live         = StatusPillPalette(background: Color(hex: "fee2e2"), foreground: Color(hex: "ef4444"))
    static let final        = StatusPillPalette(background: Color(hex: "e5e7eb"), foreground: Color(hex: "374151"))
    static let scheduled    = StatusPillPalette(background: Color(hex: "dbeafe"), foreground: Color(hex: "2563eb"))
    static let out          = StatusPillPalette(background: Color(hex: "fee2e2"), foreground: Color(hex: "dc2626"))
    static let doubtful     = StatusPillPalette(background: Color(hex: "ffedd5"), foreground: Color(hex: "ea580c"))
    static let questionable = StatusPillPalette(background: Color(hex: "fef3c7"), foreground: Color(hex: "ca8a04"))
}

// MARK: - Typography

extension Font {
    // Editorial serif — Instrument Serif when bundled, falls back to system serif.
    static func csEditorial(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .serif)
    }

    // Body — Inter when bundled, falls back to SF Pro.
    static func csBody(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .default)
    }

    // Numbers — JetBrains Mono when bundled, falls back to SF Mono.
    static func csMono(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }

    // Uppercase tracked section header (11pt, 700).
    static let csSection: Font = .system(size: 11, weight: .bold, design: .default)
}
