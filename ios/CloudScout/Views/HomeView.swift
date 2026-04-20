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
                    // Header
                    HStack {
                        Text("Feed")
                            .font(.system(size: 20, weight: .bold)).foregroundColor(.white)
                        Spacer()
                        Button { Task { await loadAll() } } label: {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 15, weight: .semibold)).foregroundColor(.appPrimary)
                        }
                    }
                    .padding(.horizontal, 16).padding(.vertical, 12)

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
                            VStack(spacing: 16) {
                                // Today's Live Games Section
                                if !todayGames.isEmpty {
                                    VStack(alignment: .leading, spacing: 10) {
                                        Text("🔴 Live Today")
                                            .font(.system(size: 14, weight: .semibold)).foregroundColor(.appPrimary)
                                        ForEach(todayGames) { game in
                                            LiveGameCard(game: game)
                                        }
                                    }
                                    .padding(.horizontal, 16)
                                }

                                // NBA Recent Games Section
                                if !nbaGames.isEmpty {
                                    VStack(alignment: .leading, spacing: 10) {
                                        Text("🏀 Latest NBA")
                                            .font(.system(size: 14, weight: .semibold)).foregroundColor(.appPrimary)
                                        ForEach(nbaGames.prefix(3)) { game in
                                            GameCard(game: game)
                                        }
                                    }
                                    .padding(.horizontal, 16)

                                    // NBA Top Performers
                                    if let perf = nbaTopPerformers, let players = perf.players, !players.isEmpty {
                                        VStack(alignment: .leading, spacing: 10) {
                                            Text("⭐ NBA Stars")
                                                .font(.system(size: 14, weight: .semibold)).foregroundColor(.appPrimary)
                                            ForEach(players.prefix(3)) { player in
                                                NBAPerformerCard(player: player)
                                            }
                                        }
                                        .padding(.horizontal, 16)
                                    }
                                }

                                // MLB Recent Games Section
                                if !mlbGames.isEmpty {
                                    VStack(alignment: .leading, spacing: 10) {
                                        Text("⚾ Latest MLB")
                                            .font(.system(size: 14, weight: .semibold)).foregroundColor(.appMLB)
                                        ForEach(mlbGames.prefix(3)) { game in
                                            GameCard(game: game)
                                        }
                                    }
                                    .padding(.horizontal, 16)

                                    // MLB Top Performers
                                    if let perf = mlbTopPerformers, (!(perf.batters ?? []).isEmpty || !(perf.pitchers ?? []).isEmpty) {
                                        VStack(alignment: .leading, spacing: 10) {
                                            Text("🔥 MLB Standouts")
                                                .font(.system(size: 14, weight: .semibold)).foregroundColor(.appMLB)
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
                                        .padding(.horizontal, 16)
                                    }
                                }

                                Spacer(minLength: 20)
                            }
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

        async let nba = Task {
            do {
                self.nbaGames = try await API.games(league: .NBA, limit: 5).sorted { $0.date > $1.date }
                self.nbaTopPerformers = try await API.topPerformers(league: .NBA, n: 10)
            } catch let e {
                error = e.localizedDescription
            }
        }

        async let mlb = Task {
            do {
                self.mlbGames = try await API.games(league: .MLB, limit: 5).sorted { $0.date > $1.date }
                self.mlbTopPerformers = try await API.topPerformers(league: .MLB, n: 10)
            } catch let e {
                error = e.localizedDescription
            }
        }

        async let today = Task {
            do {
                self.todayGames = try await API.todaysGames()
            } catch {
                // Silently fail if today's games unavailable
            }
        }

        _ = await (nba, mlb, today)
        loading = false
    }
}

// MARK: - Live Game Card (for today's games)
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

// MARK: - NBA Performer Card
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

// MARK: - MLB Batter Card
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

// MARK: - MLB Pitcher Card
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

// MARK: - Helper: Stat Badge
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
