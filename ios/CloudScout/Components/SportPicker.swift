import SwiftUI

struct SportPicker: View {
    @Binding var sport: Sport

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Sport.allCases) { s in
                Button {
                    sport = s
                } label: {
                    Text(s.rawValue)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(sport == s ? .white : .appSub)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 7)
                        .background(sport == s ? (s == .NBA ? Color.appPrimary : Color.appMLB) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                }
            }
        }
        .padding(3)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder, lineWidth: 1))
        .padding(.bottom, 12)
    }
}
