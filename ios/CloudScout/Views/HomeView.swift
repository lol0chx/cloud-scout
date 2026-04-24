import SwiftUI

struct HomeView: View {
    @EnvironmentObject var state: AppState
    @State private var nbaGames: [Game] = []
    @State private var mlbGames: [Game] = []
    @State private var todayGames: [TodayGame] = []
    @State private var nbaTopPerformers: TopPerformersResponse?
    @State private var mlbTopPerformers: TopPerformersResponse?
    @State private var nbaTeams: [String] = []
    @State private var mlbTeams: [String] = []
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.feedBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    HStack(alignment: .firstTextBaseline) {
                        Text("Feed")
                            .font(.system(size: 34, weight: .heavy, design: .rounded))
                            .foregroundColor(.feedText)
                        Spacer()
                        Button { Task { await loadAll() } } label: {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 17, weight: .semibold)).foregroundColor(.feedNBA)
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 14)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.feedLive).padding()
                    } else if loading && nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer(); ProgressView().tint(.feedNBA); Spacer()
                    } else if nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "chart.line.uptrend").font(.system(size: 40)).foregroundColor(.feedBorder)
                            Text("No games yet").font(.system(size: 16, weight: .semibold)).foregroundColor(.feedSub)
                            Text("Go to Update tab to scrape data").font(.system(size: 13)).foregroundColor(.feedBorder)
                        }
                        Spacer()
                    } else {
                        ScrollView(.vertical, showsIndicators: false) {
                            VStack(spacing: 12) {
                                ForEach(todayGames) { game in
                                    Button {
                                        state.pendingPredictMatchup = PredictMatchup(
                                            sport: .NBA,
                                            homeTeam: game.home_team_full,
                                            awayTeam: game.away_team_full
                                        )
                                        state.sport = .NBA
                                        state.selectedTab = 3
                                    } label: {
                                        LiveGameCard(game: game)
                                    }
                                    .buttonStyle(.plain)
                                }

                                ForEach(nbaGames.prefix(3)) { game in
                                    NavigationLink { GameDetailView(game: game) } label: {
                                        FeedResultCard(game: game)
                                    }
                                    .buttonStyle(.plain)
                                }

                                if let perf = nbaTopPerformers, let players = perf.players {
                                    ForEach(players.prefix(3)) { player in
                                        NavigationLink {
                                            PlayerDetailPush(player: player.player, sport: .NBA, role: "", teams: nbaTeams)
                                        } label: {
                                            NBAPerformerCard(player: player)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }

                                ForEach(mlbGames.prefix(3)) { game in
                                    NavigationLink { GameDetailView(game: game) } label: {
                                        FeedResultCard(game: game)
                                    }
                                    .buttonStyle(.plain)
                                }

                                if let perf = mlbTopPerformers {
                                    if let batters = perf.batters {
                                        ForEach(batters.prefix(2)) { batter in
                                            NavigationLink {
                                                PlayerDetailPush(player: batter.player, sport: .MLB, role: "batter", teams: mlbTeams)
                                            } label: {
                                                MLBBatterCard(batter: batter)
                                            }
                                            .buttonStyle(.plain)
                                        }
                                    }
                                    if let pitchers = perf.pitchers {
                                        ForEach(pitchers.prefix(1)) { pitcher in
                                            NavigationLink {
                                                PlayerDetailPush(player: pitcher.player, sport: .MLB, role: "pitcher", teams: mlbTeams)
                                            } label: {
                                                MLBPitcherCard(pitcher: pitcher)
                                            }
                                            .buttonStyle(.plain)
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
            .toolbarBackground(Color.feedBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { await loadAll() }
    }

    private func loadAll() async {
        loading = true
        error = ""

        async let nbaG = API.games(league: .NBA, limit: 5)
        async let nbaP = API.topPerformers(league: .NBA, n: 10)
        async let nbaT = API.teams(league: .NBA)
        async let mlbG = API.games(league: .MLB, limit: 5)
        async let mlbP = API.topPerformers(league: .MLB, n: 10)
        async let mlbT = API.teams(league: .MLB)
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

        self.nbaTeams = (try? await nbaT) ?? []
        self.mlbTeams = (try? await mlbT) ?? []
        self.todayGames = (try? await today) ?? []
        loading = false
    }
}

// MARK: - Navigation wrappers

private struct PlayerDetailPush: View {
    let player: String
    let sport: Sport
    let role: String
    let teams: [String]
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        PlayerDetailView(player: player, sport: sport, role: role, teams: teams, onBack: { dismiss() })
    }
}

// MARK: - Card primitives

private struct FeedCardBackground: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(Color.feedCard)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .strokeBorder(Color.feedBorder, lineWidth: 1)
            )
    }
}

extension View {
    fileprivate func feedCard() -> some View { modifier(FeedCardBackground()) }
}

struct LeagueBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .bold))
            .kerning(0.6)
            .foregroundColor(color)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
    }
}

struct LiveGameCard: View {
    let game: TodayGame

    private var statusInfo: (text: String, color: Color, isLive: Bool) {
        switch game.game_status {
        case 1: return ("SCHEDULED", .feedNBA, false)
        case 2: return ("LIVE", .feedLive, true)
        case 3: return ("FINAL", .feedSub, false)
        default: return (game.status.uppercased(), .feedSub, false)
        }
    }

    var body: some View {
        let s = statusInfo
        HStack(spacing: 0) {
            Rectangle().fill(Color.feedNBA).frame(width: 4)
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    LeagueBadge(text: "NBA", color: .feedNBA)
                    Text("Today")
                        .font(.system(size: 11, weight: .medium)).foregroundColor(.feedSub)
                    Spacer()
                    HStack(spacing: 5) {
                        if s.isLive {
                            Circle().fill(s.color).frame(width: 6, height: 6)
                        }
                        Text(s.text)
                            .font(.system(size: 10, weight: .bold)).kerning(0.5)
                            .foregroundColor(s.color)
                    }
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(s.color.opacity(0.12))
                    .clipShape(Capsule())
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text(game.away_team_full)
                        .font(.system(size: 17, weight: .semibold)).foregroundColor(.feedText)
                        .lineLimit(1)
                    HStack(spacing: 6) {
                        Text("@")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.feedNBA)
                        Text(game.home_team_full)
                            .font(.system(size: 17, weight: .semibold)).foregroundColor(.feedText)
                            .lineLimit(1)
                    }
                }
            }
            .padding(16)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .feedCard()
    }
}

struct FeedResultCard: View {
    let game: Game

    private var homeWon: Bool { game.home_score > game.away_score }
    private var awayWon: Bool { game.away_score > game.home_score }
    private var leagueColor: Color { game.league == "MLB" ? .feedMLB : .feedNBA }
    private var unitLabel: String { game.league == "MLB" ? "run" : "pt" }
    private var margin: Int { abs(game.home_score - game.away_score) }

    private var formattedDate: String {
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        guard let d = inFmt.date(from: game.date) else { return game.date }
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: d), to: Calendar.current.startOfDay(for: Date())).day ?? 0
        switch days {
        case 0: return "Today"
        case 1: return "Yesterday"
        case 2...6: return "\(days) days ago"
        default:
            let out = DateFormatter()
            out.dateFormat = "MMM d"
            return out.string(from: d)
        }
    }

    var body: some View {
        HStack(spacing: 0) {
            Rectangle().fill(leagueColor).frame(width: 4)
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    LeagueBadge(text: game.league, color: leagueColor)
                    Text(formattedDate)
                        .font(.system(size: 11, weight: .medium)).foregroundColor(.feedSub)
                    Spacer()
                    Text("FINAL")
                        .font(.system(size: 10, weight: .bold)).kerning(0.5)
                        .foregroundColor(leagueColor)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(leagueColor.opacity(0.12))
                        .clipShape(Capsule())
                }

                VStack(spacing: 8) {
                    teamRow(name: game.away_team, score: game.away_score, won: awayWon)
                    teamRow(name: game.home_team, score: game.home_score, won: homeWon)
                }

                HStack(spacing: 4) {
                    Text("Margin")
                        .font(.system(size: 10, weight: .medium)).foregroundColor(.feedBorder)
                    Text("\(margin) \(unitLabel)\(margin == 1 ? "" : "s")")
                        .font(.system(size: 10, weight: .semibold)).foregroundColor(.feedSub)
                }
            }
            .padding(16)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .feedCard()
    }

    @ViewBuilder
    private func teamRow(name: String, score: Int, won: Bool) -> some View {
        HStack(spacing: 10) {
            Circle()
                .fill(won ? leagueColor : Color.clear)
                .frame(width: 6, height: 6)
            Text(name)
                .font(.system(size: 16, weight: won ? .semibold : .regular))
                .foregroundColor(won ? .feedText : .feedSub)
                .lineLimit(1)
            Spacer()
            Text("\(score)")
                .font(.system(size: 22, weight: won ? .bold : .regular, design: .rounded))
                .foregroundColor(won ? leagueColor : .feedSub)
                .monospacedDigit()
        }
    }
}

struct NBAPerformerCard: View {
    let player: NBATopPlayer

    var body: some View {
        PlayerCardShell(name: player.player, subtitle: "\(player.games) games", accent: .feedNBA) {
            HStack(spacing: 12) {
                StatBadge(value: String(format: "%.1f", player.avg_points), label: "PPG", color: .feedNBA)
                StatBadge(value: String(format: "%.1f", player.avg_assists), label: "APG", color: .feedNBA)
                StatBadge(value: String(format: "%.1f", player.avg_rebounds), label: "RPG", color: .feedNBA)
            }
        }
    }
}

struct MLBBatterCard: View {
    let batter: MLBBatter

    var body: some View {
        PlayerCardShell(name: batter.player, subtitle: "\(batter.games) games", accent: .feedMLB) {
            HStack(spacing: 12) {
                StatBadge(value: String(format: "%.3f", batter.AVG), label: "AVG", color: .feedMLB)
                StatBadge(value: "\(batter.HR)", label: "HR", color: .feedMLB)
                StatBadge(value: "\(batter.RBI)", label: "RBI", color: .feedMLB)
            }
        }
    }
}

struct MLBPitcherCard: View {
    let pitcher: MLBPitcher

    var body: some View {
        PlayerCardShell(name: pitcher.player, subtitle: "\(pitcher.games) games", accent: .feedMLB) {
            HStack(spacing: 12) {
                StatBadge(value: String(format: "%.2f", pitcher.ERA), label: "ERA", color: .feedMLB)
                StatBadge(value: String(format: "%.2f", pitcher.WHIP), label: "WHIP", color: .feedMLB)
                StatBadge(value: "\(pitcher.SO)", label: "K", color: .feedMLB)
            }
        }
    }
}

struct PlayerCardShell<Stats: View>: View {
    let name: String
    let subtitle: String
    let accent: Color
    @ViewBuilder let stats: () -> Stats

    var body: some View {
        HStack(spacing: 0) {
            Rectangle().fill(accent).frame(width: 4)
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(name)
                        .font(.system(size: 13, weight: .semibold)).foregroundColor(.feedText)
                    Text(subtitle)
                        .font(.system(size: 11)).foregroundColor(.feedSub)
                }
                Spacer()
                stats()
            }
            .padding(14)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .feedCard()
    }
}

struct StatBadge: View {
    let value: String
    let label: String
    var color: Color = .feedNBA

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 11, weight: .semibold)).foregroundColor(color)
            Text(label)
                .font(.system(size: 9)).foregroundColor(.feedSub)
        }
    }
}

#Preview {
    HomeView()
        .environmentObject(AppState())
}
