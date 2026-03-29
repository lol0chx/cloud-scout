import SwiftUI

struct StandingsView: View {
    @EnvironmentObject var state: AppState
    @State private var standings: [Standing] = []
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.appBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Standings")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.bottom, 12)
                        SportPicker(sport: $state.sport)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding()
                    } else {
                        // Header
                        HStack {
                            Text("Team").frame(maxWidth: .infinity, alignment: .leading)
                            Text("W").frame(width: 36, alignment: .center)
                            Text("L").frame(width: 36, alignment: .center)
                            Text("Win%").frame(width: 48, alignment: .center)
                            Text("Net").frame(width: 54, alignment: .center)
                            Text("Str").frame(width: 36, alignment: .center)
                        }
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.appSub)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.appBg)
                        Divider().background(Color.appBorder)

                        if loading && standings.isEmpty {
                            Spacer()
                            ProgressView().tint(.appPrimary)
                            Spacer()
                        } else {
                            List(Array(standings.enumerated()), id: \.element.id) { idx, s in
                                StandingRow(standing: s, rank: idx + 1)
                                    .listRowBackground(idx % 2 == 0 ? Color.appCard.opacity(0.4) : Color.clear)
                                    .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))
                                    .listRowSeparatorTint(Color.appBorder)
                            }
                            .listStyle(.plain)
                            .refreshable { await load() }
                        }
                    }
                }
            }
        }
        .task { await load() }
        .onChange(of: state.sport) { _, _ in Task { await load() } }
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

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                Text("\(rank)").font(.system(size: 12)).foregroundColor(.appSub).frame(width: 20)
                Text(standing.Team).font(.system(size: 13)).foregroundColor(.white).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text("\(standing.W)").cell()
            Text("\(standing.L)").cell()
            Text(String(format: "%.0f%%", standing.winPct)).cell()
            Text(String(format: "%+.1f", standing.netRtg))
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(standing.netRtg > 0 ? .appWin : standing.netRtg < 0 ? .appLoss : .white)
                .frame(width: 54, alignment: .center)
            Text(standing.Streak)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(standing.Streak.hasPrefix("W") ? .appWin : .appLoss)
                .frame(width: 36, alignment: .center)
        }
        .padding(.vertical, 10)
    }
}

private extension Text {
    func cell() -> some View {
        self.font(.system(size: 13)).foregroundColor(.white).frame(width: 36, alignment: .center)
    }
}
