import SwiftUI

struct PredictView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var teamA = ""
    @State private var teamB = ""
    @State private var result: Prediction?
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Predictions")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.bottom, 12)
                    SportPicker(sport: $state.sport)

                    HStack(alignment: .bottom, spacing: 8) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Team A").font(.system(size: 12)).foregroundColor(.appSub)
                            Picker("Team A", selection: $teamA) {
                                ForEach(teams, id: \.self) { Text($0).tag($0) }
                            }
                            .pickerStyle(.menu).tint(.appSub)
                            .frame(maxWidth: .infinity)
                            .padding(8)
                            .background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        Text("vs").foregroundColor(.appSub).padding(.bottom, 12)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Team B").font(.system(size: 12)).foregroundColor(.appSub)
                            Picker("Team B", selection: $teamB) {
                                ForEach(teams, id: \.self) { Text($0).tag($0) }
                            }
                            .pickerStyle(.menu).tint(.appSub)
                            .frame(maxWidth: .infinity)
                            .padding(8)
                            .background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                    .padding(.bottom, 12)

                    if teamA == teamB && !teamA.isEmpty {
                        Text("Select two different teams.")
                            .font(.system(size: 13))
                            .foregroundColor(.appMLB)
                            .padding(.bottom, 8)
                    }

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding(.top, 20)
                    } else if loading && result == nil {
                        HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 40)
                    } else if let p = result {
                        PredictionResult(prediction: p, isMLB: state.sport == .MLB)
                    }
                }
                .padding(16)
            }
            .refreshable { await load() }
            .background(Color.appBg.ignoresSafeArea())
        }
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: teamA) { _, _ in Task { await load() } }
        .onChange(of: teamB) { _, _ in Task { await load() } }
    }

    private func loadTeams() async {
        result = nil
        do {
            teams = try await API.teams(league: state.sport)
            if teams.count >= 2 { teamA = teams[0]; teamB = teams[1] }
        } catch { teams = [] }
        await load()
    }

    private func load() async {
        guard !teamA.isEmpty, !teamB.isEmpty, teamA != teamB else { return }
        loading = true; error = ""
        do { result = try await API.prediction(league: state.sport, teamA: teamA, teamB: teamB) }
        catch let e { error = e.localizedDescription; result = nil }
        loading = false
    }
}

private struct PredictionResult: View {
    let prediction: Prediction
    let isMLB: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionHeader("Win Probability")
            HStack(spacing: 10) {
                ProbCard(team: prediction.team_a, pct: prediction.prob_a, winning: prediction.prob_a >= prediction.prob_b)
                ProbCard(team: prediction.team_b, pct: prediction.prob_b, winning: prediction.prob_b > prediction.prob_a)
            }
            .padding(.bottom, 4)

            SectionHeader(isMLB ? "Run Line" : "Spread")
            VStack {
                if prediction.margin > 0 {
                    (Text(prediction.team_a).foregroundColor(.appPrimary) +
                     Text(" favored by ") +
                     Text(String(format: "%.1f %@", abs(prediction.margin), isMLB ? "runs" : "pts")).bold())
                } else if prediction.margin < 0 {
                    (Text(prediction.team_b).foregroundColor(.appPrimary) +
                     Text(" favored by ") +
                     Text(String(format: "%.1f %@", abs(prediction.margin), isMLB ? "runs" : "pts")).bold())
                } else {
                    Text("Pick 'em")
                }
            }
            .font(.system(size: 15))
            .foregroundColor(.appSub)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.appCard)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .padding(.bottom, 4)

            SectionHeader("Context")
            HStack(spacing: 10) {
                ContextCard(team: prediction.team_a, record: prediction.team_a_record, streak: prediction.team_a_streak)
                ContextCard(team: prediction.team_b, record: prediction.team_b_record, streak: prediction.team_b_streak)
            }
        }
    }
}

private struct ProbCard: View {
    let team: String
    let pct: Double
    let winning: Bool

    var body: some View {
        VStack(spacing: 4) {
            Text(String(format: "%.0f%%", pct))
                .font(.system(size: 32, weight: .heavy))
                .foregroundColor(.white)
            Text(team)
                .font(.system(size: 12))
                .foregroundColor(.white.opacity(0.9))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(16)
        .background(winning ? Color.appWin : Color.appLoss)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct ContextCard: View {
    let team: String
    let record: TeamRecord
    let streak: TeamStreak

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(team).font(.system(size: 13, weight: .semibold)).foregroundColor(.white).lineLimit(2)
            Text("\(record.wins)W – \(record.losses)L").font(.system(size: 12)).foregroundColor(.appSub)
            Text(String(format: "%.0f%% win", record.win_pct)).font(.system(size: 12)).foregroundColor(.appSub)
            Text("\(streak.type)\(streak.count) streak")
                .font(.system(size: 12))
                .foregroundColor(streak.type == "W" ? .appWin : .appLoss)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct SectionHeader: View {
    let title: String
    init(_ title: String) { self.title = title }
    var body: some View {
        Text(title.uppercased())
            .font(.system(size: 12, weight: .semibold))
            .foregroundColor(.appSub)
            .kerning(0.8)
            .padding(.top, 16)
            .padding(.bottom, 8)
    }
}
