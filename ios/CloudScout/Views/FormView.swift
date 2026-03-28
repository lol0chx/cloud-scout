import SwiftUI

struct FormView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var team = ""
    @State private var form: TeamForm?
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Team Form")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.bottom, 12)
                    SportPicker(sport: $state.sport)

                    Picker("Team", selection: $team) {
                        ForEach(teams, id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.menu)
                    .tint(.appSub)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.bottom, 12)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding(.top, 20)
                    } else if loading && form == nil {
                        HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 40)
                    } else if let f = form {
                        let isMLB = state.sport == .MLB
                        let streakColor: Color = f.streak_type == "W" ? .appWin : .appLoss
                        let netColor: Color = f.net_rating >= 0 ? .appWin : .appLoss

                        // Stat cards
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                            StatCard(label: "Games", value: "\(f.games)")
                            StatCard(label: "Streak", value: "\(f.streak_type)\(f.streak_count)", color: streakColor)
                            StatCard(label: isMLB ? "Avg Runs" : "Avg Scored", value: "\(f.avg_scored)")
                            StatCard(label: isMLB ? "Avg Allowed" : "Avg Conceded", value: "\(f.avg_conceded)")
                            StatCard(
                                label: isMLB ? "Run Diff" : "Net Rating",
                                value: String(format: "%+.1f", f.net_rating),
                                color: netColor
                            )
                        }
                        .padding(.bottom, 8)

                        Text("GAME LOG")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.appSub)
                            .kerning(0.8)
                            .padding(.top, 8)
                            .padding(.bottom, 8)

                        ForEach(f.form_log) { g in
                            FormGameRow(game: g)
                        }
                    }
                }
                .padding(16)
            }
            .refreshable { await load() }
            .background(Color.appBg.ignoresSafeArea())
        }
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: team) { _, _ in Task { await load() } }
    }

    private func loadTeams() async {
        form = nil
        do {
            teams = try await API.teams(league: state.sport)
            if let first = teams.first { team = first }
        } catch { teams = [] }
        await load()
    }

    private func load() async {
        guard !team.isEmpty else { return }
        loading = true; error = ""
        do { form = try await API.teamForm(league: state.sport, team: team) }
        catch let e { error = e.localizedDescription; form = nil }
        loading = false
    }
}

private struct StatCard: View {
    let label: String
    let value: String
    var color: Color = .white

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.system(size: 12)).foregroundColor(.appSub)
            Text(value).font(.system(size: 16, weight: .semibold)).foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct FormGameRow: View {
    let game: FormGame

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text("\(game.location == "Home" ? "vs" : "@") \(game.opponent)")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.white)
                    .lineLimit(1)
                Text(game.date).font(.system(size: 11)).foregroundColor(.appSub)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text(game.result)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(game.result == "W" ? .appWin : .appLoss)
                .frame(width: 20)
            Text("\(game.scored)–\(game.conceded)")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 55, alignment: .center)
            Text(String(format: "%.1f", game.rolling_avg))
                .font(.system(size: 12))
                .foregroundColor(.appSub)
                .frame(width: 36, alignment: .trailing)
        }
        .padding(10)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 3)
                .fill(game.result == "W" ? Color.appWin : Color.appLoss)
                .frame(width: 3)
        }
        .padding(.bottom, 6)
    }
}
