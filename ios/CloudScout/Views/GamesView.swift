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
                        HStack {
                            Text("Game Results")
                                .font(.system(size: 20, weight: .bold)).foregroundColor(.white)
                            Spacer()
                            Button { Task { await load() } } label: {
                                Image(systemName: "arrow.clockwise")
                                    .font(.system(size: 15, weight: .semibold)).foregroundColor(.appPrimary)
                            }
                        }
                        .padding(.bottom, 12)
                        SportPicker(sport: $state.sport)
                        Picker("Team", selection: $team) {
                            Text("All Teams").tag("")
                            ForEach(teams, id: \.self) { Text($0).tag($0) }
                        }
                        .pickerStyle(.menu).tint(.appSub)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.bottom, 8)
                    }
                    .padding(.horizontal, 16).padding(.top, 16)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding()
                    } else if loading && games.isEmpty {
                        Spacer(); ProgressView().tint(.appPrimary); Spacer()
                    } else if games.isEmpty {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "sportscourt").font(.system(size: 40)).foregroundColor(.appBorder)
                            Text("No games yet").font(.system(size: 16, weight: .semibold)).foregroundColor(.appSub)
                            Text("Go to Update tab to scrape data").font(.system(size: 13)).foregroundColor(.appBorder)
                        }
                        Spacer()
                    } else {
                        List(games) { game in
                            NavigationLink(destination: GameDetailView(game: game, selectedTeam: team)) {
                                GameCard(game: game, selectedTeam: team)
                            }
                            .listRowBackground(Color.appBg)
                            .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                            .listRowSeparator(.hidden)
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
        loading = true; error = ""
        do { games = try await API.games(league: state.sport, team: team).sorted { $0.date > $1.date } }
        catch let e { error = e.localizedDescription }
        loading = false
    }
}

struct GameCard: View {
    let game: Game
    var selectedTeam: String = ""

    private var homeWon: Bool { game.home_score > game.away_score }
    private var isTeamGame: Bool { !selectedTeam.isEmpty && (game.home_team == selectedTeam || game.away_team == selectedTeam) }
    private var isHome: Bool { game.home_team == selectedTeam }
    private var teamWon: Bool { isHome ? homeWon : !homeWon }
    private var resultColor: Color { isTeamGame ? (teamWon ? .appWin : .appLoss) : .appSub }

    var body: some View {
        HStack(spacing: 10) {
            // Left accent bar
            if isTeamGame {
                RoundedRectangle(cornerRadius: 2).fill(resultColor).frame(width: 3)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(game.date).font(.system(size: 11)).foregroundColor(.appSub)

                HStack(spacing: 6) {
                    Text(game.home_team)
                        .font(.system(size: 13, weight: homeWon ? .semibold : .regular))
                        .foregroundColor(homeWon ? .white : .appSub)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Text("\(game.home_score)–\(game.away_score)")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(.white)
                        .fixedSize()

                    Text(game.away_team)
                        .font(.system(size: 13, weight: !homeWon ? .semibold : .regular))
                        .foregroundColor(!homeWon ? .white : .appSub)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }

                if isTeamGame {
                    HStack(spacing: 4) {
                        Text(teamWon ? "W" : "L")
                            .font(.system(size: 11, weight: .bold)).foregroundColor(resultColor)
                        Text("·").foregroundColor(.appBorder)
                        Text(isHome ? "Home" : "Away")
                            .font(.system(size: 11)).foregroundColor(.appSub)
                        Spacer()
                        Text("\(abs(game.home_score - game.away_score)) \(game.league == "MLB" ? "run" : "pt") margin")
                            .font(.system(size: 11)).foregroundColor(.appSub)
                    }
                }
            }
        }
        .padding(12)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
