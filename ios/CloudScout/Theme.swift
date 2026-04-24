import SwiftUI

extension Color {
    static let appBg      = Color(hex: "0d0d0d")
    static let appCard    = Color(hex: "1c1c2e")
    static let appBorder  = Color(hex: "2a2a3e")
    static let appPrimary = Color(hex: "5b8ff7")
    static let appWin     = Color(hex: "2ea44f")
    static let appLoss    = Color(hex: "cf222e")
    static let appSub     = Color(hex: "8a8a9a")
    static let appMLB     = Color(hex: "f4c742")

    // Feed (light look — used only in HomeView)
    static let feedBg     = Color(hex: "eef0f3")
    static let feedCard   = Color(hex: "ffffff")
    static let feedBorder = Color(hex: "e8eaee")
    static let feedChip   = Color(hex: "f1f3f5")
    static let feedText   = Color(hex: "0f172a")
    static let feedSub    = Color(hex: "64748b")
    static let feedNBA    = Color(hex: "2563eb")
    static let feedMLB    = Color(hex: "d97706")
    static let feedLive   = Color(hex: "ef4444")

    init(hex: String) {
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8)  & 0xFF) / 255
        let b = Double( int        & 0xFF) / 255
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1)
    }
}
