import SwiftUI

struct HomeView: View {
    @EnvironmentObject var state: AppState
    @State private var nbaGames: [Game] = []
    @State private var mlbGames: [Game] = []
    @State private var todayGames: [TodayGame] = []
    @State private var nbaTopPerformers: TopPerformersResponse?
    @State private var mlbTopPerformers: TopPerformersResponse?
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.appBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    HStack(alignment: .firstTextBaseline) {
                        Text("Feed")
                            .font(.system(size: 34, weight: .heavy, design: .rounded))
                            .foregroundColor(.white)
                        Spacer()
                        Button { Task { await loadAll() } } label: {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 17, weight: .semibold)).foregroundColor(.appPrimary)
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 14)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding()
                    } else if loading && nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer(); ProgressView().tint(.appPrimary); Spacer()
                    } else if nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "chart.line.uptrend").font(.system(size: 40)).foregroundColor(.appBorder)
                            Text("No games yet").font(.system(size: 16, weight: .semibold)).foregroundColor(.appSub)
                            Text("Go to Update tab to scrape data").font(.system(size: 13)).foregroundColor(.appBorder)
                        }
                        Spacer()
                    } else {
                        ScrollView(.vertical, showsIndicators: false) {
                            VStack(spacing: 10) {
                                ForEach(todayGames) { game in
                                    LiveGameCard(game: game)
                                }

                                ForEach(nbaGames.prefix(3)) { game in
                                    GameCard(game: game)
                                }

                                if let perf = nbaTopPerformers, let players = perf.players {
                                    ForEach(players.prefix(3)) { player in
                                        NBAPerformerCard(player: player)
                                    }
                                }

                                ForEach(mlbGames.prefix(3)) { game in
                                    GameCard(game: game)
                                }

                                if let perf = mlbTopPerformers {
                                    if let batters = perf.batters {
                                        ForEach(batters.prefix(2)) { batter in
                                            MLBBatterCard(batter: batter)
                                        }
                                    }
                                    if let pitchers = perf.pitchers {
                                        ForEach(pitchers.prefix(1)) { pitcher in
                                            MLBPitcherCard(pitcher: pitcher)
                                        }
                                    }
                                }

                                Spacer(minLength: 20)
                            }
                            .padding(.horizontal, 16)
                        }
                    }
                }
            }
        }
        .task { await loadAll() }
    }

    private func loadAll() async {
        loading = true
        error = ""

        async let nbaG = API.games(league: .NBA, limit: 5)
        async let nbaP = API.topPerformers(league: .NBA, n: 10)
        async let mlbG = API.games(league: .MLB, limit: 5)
        async let mlbP = API.topPerformers(league: .MLB, n: 10)
        async let today = API.todaysGames()

        do {
            self.nbaGames = try await nbaG.sorted { $0.date > $1.date }
            self.nbaTopPerformers = try await nbaP
        } catch {
            self.error = error.localizedDescription
        }

        do {
            self.mlbGames = try await mlbG.sorted { $0.date > $1.date }
            self.mlbTopPerformers = try await mlbP
        } catch {
            self.error = error.localizedDescription
        }

        self.todayGames = (try? await today) ?? []
        loading = false
    }
}

struct LiveGameCard: View {
    let game: TodayGame

    var statusText: String {
        switch game.game_status {
        case 1: return "Scheduled"
        case 2: return "🔴 Live"
        case 3: return "Final"
        default: return game.status
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text(game.away_team_full)
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                Text(game.home_team_full)
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
            }
            Spacer()
            VStack(alignment: .center, spacing: 4) {
                Text(statusText)
                    .font(.system(size: 10, weight: .semibold)).foregroundColor(
                        game.game_status == 2 ? .appPrimary : .appSub
                    )
                if game.game_status == 2 {
                    Image(systemName: "circle.fill")
                        .font(.system(size: 6)).foregroundColor(.red)
                        .animation(.easeInOut(duration: 1).repeatForever(), value: UUID())
                }
            }
        }
        .padding(12)
        .background(Color.appCard)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder, lineWidth: 1))
    }
}

struct NBAPerformerCard: View {
    let player: NBATopPlayer

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(player.player)
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                Text("\(player.games) games")
                    .font(.system(size: 11)).foregroundColor(.appSub)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 12) {
                    StatBadge(value: String(format: "%.1f", player.avg_points), label: "PPG")
                    StatBadge(value: String(format: "%.1f", player.avg_assists), label: "APG")
                    StatBadge(value: String(format: "%.1f", player.avg_rebounds), label: "RPG")
                }
            }
        }
        .padding(12)
        .background(Color.appCard)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder, lineWidth: 1))
    }
}

struct MLBBatterCard: View {
    let batter: MLBBatter

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(batter.player)
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                Text("\(batter.games) games")
                    .font(.system(size: 11)).foregroundColor(.appSub)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 12) {
                    StatBadge(value: String(format: "%.3f", batter.AVG), label: "AVG")
                    StatBadge(value: "\(batter.HR)", label: "HR")
                    StatBadge(value: "\(batter.RBI)", label: "RBI")
                }
            }
        }
        .padding(12)
        .background(Color.appCard)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder, lineWidth: 1))
    }
}

struct MLBPitcherCard: View {
    let pitcher: MLBPitcher

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(pitcher.player)
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                Text("\(pitcher.games) games")
                    .font(.system(size: 11)).foregroundColor(.appSub)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 12) {
                    StatBadge(value: String(format: "%.2f", pitcher.ERA), label: "ERA")
                    StatBadge(value: String(format: "%.2f", pitcher.WHIP), label: "WHIP")
                    StatBadge(value: "\(pitcher.SO)", label: "K")
                }
            }
        }
        .padding(12)
        .background(Color.appCard)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder, lineWidth: 1))
    }
}

struct StatBadge: View {
    let value: String
    let label: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 11, weight: .semibold)).foregroundColor(.appPrimary)
            Text(label)
                .font(.system(size: 9)).foregroundColor(.appSub)
        }
    }
}

#Preview {
    HomeView()
        .environmentObject(AppState())
}
