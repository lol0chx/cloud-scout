import SwiftUI

struct StandingsView: View {
    @EnvironmentObject var state: AppState
    @State private var standings: [Standing] = []
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.csBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    header
                        .padding(.horizontal, 18)
                        .padding(.top, 4)
                        .padding(.bottom, 14)

                    SportToggle(sport: $state.sport)
                        .padding(.horizontal, 16)
                        .padding(.bottom, 12)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.csLive).padding()
                        Spacer()
                    } else if loading && standings.isEmpty {
                        Spacer(); ProgressView().tint(.csNBA); Spacer()
                    } else {
                        ScrollView(.vertical, showsIndicators: false) {
                            VStack(spacing: 0) {
                                columnHeader
                                Divider().background(Color.csBorder)
                                ForEach(Array(standings.enumerated()), id: \.element.id) { idx, s in
                                    StandingRow(
                                        standing: s,
                                        rank: idx + 1,
                                        maxAbsNet: maxAbsNet,
                                        league: state.sport.rawValue,
                                        highlighted: idx < 4
                                    )
                                    if idx < standings.count - 1 {
                                        Divider().background(Color.csBorder)
                                    }
                                }
                            }
                            .background(Color.csCard)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .padding(.horizontal, 16)
                            .padding(.bottom, 20)
                        }
                        .refreshable { await load() }
                    }
                }
            }
            .toolbarBackground(Color.csBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { await load() }
        .onChange(of: state.sport) { _, _ in Task { await load() } }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 2) {
                Text("LEAGUE TABLE")
                    .font(.csSection)
                    .kerning(1.0)
                    .foregroundColor(.csSub)
                Text("Standings")
                    .font(.csEditorial(40))
                    .foregroundColor(.csText)
            }
            Spacer()
            Button { Task { await load() } } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.csNBA)
                    .frame(width: 36, height: 36)
                    .background(Color.csCard)
                    .clipShape(Circle())
                    .overlay(Circle().strokeBorder(Color.csBorder, lineWidth: 1))
            }
        }
    }

    private var columnHeader: some View {
        HStack(spacing: 0) {
            Text("#").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 24, alignment: .leading)
            Text("TEAM").font(.csSection).kerning(1.0).foregroundColor(.csSub)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("W").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 28, alignment: .center)
            Text("L").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 28, alignment: .center)
            Text("PCT").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 42, alignment: .center)
            Text("NET").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 64, alignment: .center)
            Text("STR").font(.csSection).kerning(0.8).foregroundColor(.csSub)
                .frame(width: 36, alignment: .trailing)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.csCard)
    }

    private var maxAbsNet: Double {
        standings.map { abs($0.netRtg) }.max() ?? 1
    }

    private func load() async {
        loading = true; error = ""
        do { standings = try await API.standings(league: state.sport) }
        catch let e { error = e.localizedDescription }
        loading = false
    }
}

private struct StandingRow: View {
    let standing: Standing
    let rank: Int
    let maxAbsNet: Double
    let league: String
    let highlighted: Bool

    var body: some View {
        HStack(spacing: 0) {
            Text("\(rank)")
                .font(.csMono(13, weight: .semibold))
                .foregroundColor(.csSub)
                .frame(width: 24, alignment: .leading)
            HStack(spacing: 8) {
                TeamBadge(team: standing.Team, league: league, size: 22)
                Text(standing.Team)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.csText)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text("\(standing.W)").cell()
            Text("\(standing.L)").cell()
            Text(String(format: "%.0f%%", standing.winPct)).cell(width: 42)
            NetRatingBar(value: standing.netRtg, maxAbs: maxAbsNet)
                .frame(width: 64, height: 22)
            Text(standing.Streak)
                .font(.csMono(13, weight: .bold))
                .foregroundColor(standing.Streak.hasPrefix("W") ? .csWin : .csLoss)
                .frame(width: 36, alignment: .trailing)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(highlighted ? Color.csNBA.opacity(0.06) : Color.clear)
    }
}

private struct NetRatingBar: View {
    let value: Double
    let maxAbs: Double

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let half = w / 2
            let ratio = maxAbs > 0 ? min(1, abs(value) / maxAbs) : 0
            let barW = half * ratio
            ZStack(alignment: .center) {
                RoundedRectangle(cornerRadius: 3).fill(Color.csChip)
                    .frame(height: 6)
                HStack(spacing: 0) {
                    Spacer()
                    if value < 0 {
                        RoundedRectangle(cornerRadius: 3).fill(Color.csLoss)
                            .frame(width: barW, height: 6)
                    } else {
                        Color.clear.frame(width: 0, height: 6)
                    }
                    if value > 0 {
                        RoundedRectangle(cornerRadius: 3).fill(Color.csWin)
                            .frame(width: barW, height: 6)
                    } else {
                        Color.clear.frame(width: 0, height: 6)
                    }
                    Spacer()
                }
                .frame(width: w)
                Rectangle().fill(Color.csBorder).frame(width: 1, height: 14)
            }
        }
    }
}

private extension Text {
    func cell(width: CGFloat = 28) -> some View {
        self
            .font(.csMono(13, weight: .semibold))
            .foregroundColor(.csText)
            .frame(width: width, alignment: .center)
    }
}
