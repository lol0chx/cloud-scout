import SwiftUI

struct GamesView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var team = ""
    @State private var games: [Game] = []
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.appBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Game Results")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.bottom, 12)
                        SportPicker(sport: $state.sport)
                        Picker("Team", selection: $team) {
                            Text("All Teams").tag("")
                            ForEach(teams, id: \.self) { Text($0).tag($0) }
                        }
                        .pickerStyle(.menu)
                        .tint(.appSub)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.bottom, 8)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding()
                    } else if loading && games.isEmpty {
                        Spacer()
                        ProgressView().tint(.appPrimary)
                        Spacer()
                    } else if games.isEmpty {
                        Spacer()
                        Text("No games. Scrape data first.")
                            .foregroundColor(.appSub)
                            .multilineTextAlignment(.center)
                            .padding()
                        Spacer()
                    } else {
                        List(games) { game in
                            GameCard(game: game, selectedTeam: team)
                                .listRowBackground(Color.appBg)
                                .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                        }
                        .listStyle(.plain)
                        .refreshable { await load() }
                    }
                }
            }
        }
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: team) { _, _ in Task { await load() } }
    }

    private func loadTeams() async {
        team = ""
        do { teams = try await API.teams(league: state.sport) } catch { teams = [] }
        await load()
    }

    private func load() async {
        loading = true
        error = ""
        do { games = try await API.games(league: state.sport, team: team).sorted { $0.date > $1.date } }
        catch let e { error = e.localizedDescription }
        loading = false
    }
}

private struct GameCard: View {
    let game: Game
    let selectedTeam: String

    private var homeWon: Bool { game.home_score > game.away_score }
    private var isTeamGame: Bool { !selectedTeam.isEmpty && (game.home_team == selectedTeam || game.away_team == selectedTeam) }
    private var isHome: Bool { game.home_team == selectedTeam }
    private var teamWon: Bool { isHome ? homeWon : !homeWon }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(game.date)
                .font(.system(size: 11))
                .foregroundColor(.appSub)
            HStack {
                Text(game.home_team)
                    .font(.system(size: 13))
                    .foregroundColor(homeWon ? .white : .appSub)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .lineLimit(1)
                Text("\(game.home_score) – \(game.away_score)")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(.white)
                    .frame(minWidth: 60)
                Text(game.away_team)
                    .font(.system(size: 13))
                    .foregroundColor(!homeWon ? .white : .appSub)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .lineLimit(1)
            }
            if isTeamGame {
                Text("\(teamWon ? "W" : "L") · \(isHome ? "Home" : "Away")")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(teamWon ? .appWin : .appLoss)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.appCard)
                .overlay(
                    isTeamGame
                        ? RoundedRectangle(cornerRadius: 10)
                            .stroke(teamWon ? Color.appWin : Color.appLoss, lineWidth: 0)
                        : nil
                )
        )
        .overlay(alignment: .leading) {
            if isTeamGame {
                RoundedRectangle(cornerRadius: 3)
                    .fill(teamWon ? Color.appWin : Color.appLoss)
                    .frame(width: 3)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
