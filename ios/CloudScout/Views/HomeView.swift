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
    @State private var teamInsight: [String: TeamInsight] = [:]
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
                            LazyVStack(spacing: 10) {
                                ForEach(todayGames) { game in
                                    LiveGameCard(
                                        game: game,
                                        awayInsight: teamInsight[game.away_team_full],
                                        homeInsight: teamInsight[game.home_team_full],
                                        onSelectMatchup: {
                                            state.pendingPredictMatchup = PredictMatchup(
                                                sport: .NBA,
                                                homeTeam: game.home_team_full,
                                                awayTeam: game.away_team_full
                                            )
                                            state.sport = .NBA
                                            state.selectedTab = 3
                                        }
                                    )
                                }

                                ForEach(nbaGames.prefix(3)) { game in
                                    NavigationLink { GameDetailView(game: game) } label: {
                                        FeedResultCard(game: game, recent: nbaGames)
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
                                        FeedResultCard(game: game, recent: mlbGames)
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

        await loadTeamInsights()
    }

    private func loadTeamInsights() async {
        let teams = Set(todayGames.flatMap { [$0.home_team_full, $0.away_team_full] })
        guard !teams.isEmpty else { return }

        await withTaskGroup(of: (String, TeamInsight?).self) { group in
            for team in teams {
                group.addTask {
                    async let perf = API.topPerformers(league: .NBA, team: team, n: 15)
                    async let inj  = API.injuries(league: .NBA, team: team)
                    let top = (try? await perf)?.players?
                        .max { $0.avg_points < $1.avg_points }
                    let injured = (try? await inj)?.filter {
                        let s = $0.status.lowercased()
                        return s == "out" || s == "doubtful" || s == "questionable"
                    } ?? []
                    return (team, TeamInsight(topScorer: top, injuryCount: injured.count))
                }
            }
            for await (team, insight) in group {
                if let insight { teamInsight[team] = insight }
            }
        }
    }
}

struct TeamInsight {
    let topScorer: NBATopPlayer?
    let injuryCount: Int
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
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.feedCard)
    }
}

extension View {
    fileprivate func feedCard() -> some View { modifier(FeedCardBackground()) }
}

// MARK: - Source header (BR-style)

struct SourceHeader: View {
    let leagueAbbr: String   // "NBA" / "MLB"
    let leagueColor: Color
    let label: String        // "NBA Today", "NBA", "MLB"
    let timestamp: String    // "2h", "Today", "Apr 12"
    var showsMenu: Bool = true

    var body: some View {
        HStack(spacing: 10) {
            Text(leagueAbbr)
                .font(.system(size: 11, weight: .heavy, design: .rounded))
                .foregroundColor(.white)
                .frame(width: 36, height: 36)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(leagueColor)
                )
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.feedText)
                Text(timestamp)
                    .font(.system(size: 12))
                    .foregroundColor(.feedSub)
            }
            Spacer()
            if showsMenu {
                Image(systemName: "ellipsis")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.feedSub)
                    .frame(width: 28, height: 28)
            }
        }
    }
}

// MARK: - Footer chip (engagement-style pill)

struct FeedChip: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon).font(.system(size: 12, weight: .semibold))
            Text(text).font(.system(size: 13, weight: .semibold))
        }
        .foregroundColor(.feedSub)
        .padding(.horizontal, 12).padding(.vertical, 7)
        .background(Color.feedChip)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
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

// MARK: - Team identity (abbreviation + brand color)

struct TeamStyle {
    let abbr: String
    let color: Color

    static func lookup(_ name: String, league: String) -> TeamStyle {
        let key = name.lowercased().trimmingCharacters(in: .whitespaces)
        if league.uppercased() == "MLB", let s = mlb[key] { return s }
        if league.uppercased() == "NBA", let s = nba[key] { return s }
        let initials = name
            .split(separator: " ")
            .compactMap { $0.first.map(String.init) }
            .joined()
        let fallback = String(initials.prefix(3)).uppercased()
        return TeamStyle(
            abbr: fallback.isEmpty ? "TBD" : fallback,
            color: league.uppercased() == "MLB" ? .feedMLB : .feedNBA
        )
    }

    private static let nba: [String: TeamStyle] = [
        "atlanta hawks":          .init(abbr: "ATL", color: Color(hex: "E03A3E")),
        "boston celtics":         .init(abbr: "BOS", color: Color(hex: "007A33")),
        "brooklyn nets":          .init(abbr: "BKN", color: Color(hex: "1A1A1A")),
        "charlotte hornets":      .init(abbr: "CHA", color: Color(hex: "1D1160")),
        "chicago bulls":          .init(abbr: "CHI", color: Color(hex: "CE1141")),
        "cleveland cavaliers":    .init(abbr: "CLE", color: Color(hex: "860038")),
        "dallas mavericks":       .init(abbr: "DAL", color: Color(hex: "00538C")),
        "denver nuggets":         .init(abbr: "DEN", color: Color(hex: "0E2240")),
        "detroit pistons":        .init(abbr: "DET", color: Color(hex: "C8102E")),
        "golden state warriors":  .init(abbr: "GSW", color: Color(hex: "1D428A")),
        "houston rockets":        .init(abbr: "HOU", color: Color(hex: "CE1141")),
        "indiana pacers":         .init(abbr: "IND", color: Color(hex: "002D62")),
        "la clippers":            .init(abbr: "LAC", color: Color(hex: "C8102E")),
        "los angeles clippers":   .init(abbr: "LAC", color: Color(hex: "C8102E")),
        "los angeles lakers":     .init(abbr: "LAL", color: Color(hex: "552583")),
        "memphis grizzlies":      .init(abbr: "MEM", color: Color(hex: "5D76A9")),
        "miami heat":             .init(abbr: "MIA", color: Color(hex: "98002E")),
        "milwaukee bucks":        .init(abbr: "MIL", color: Color(hex: "00471B")),
        "minnesota timberwolves": .init(abbr: "MIN", color: Color(hex: "0C2340")),
        "new orleans pelicans":   .init(abbr: "NOP", color: Color(hex: "0C2340")),
        "new york knicks":        .init(abbr: "NYK", color: Color(hex: "006BB6")),
        "oklahoma city thunder":  .init(abbr: "OKC", color: Color(hex: "007AC1")),
        "orlando magic":          .init(abbr: "ORL", color: Color(hex: "0077C0")),
        "philadelphia 76ers":     .init(abbr: "PHI", color: Color(hex: "006BB6")),
        "phoenix suns":           .init(abbr: "PHX", color: Color(hex: "1D1160")),
        "portland trail blazers": .init(abbr: "POR", color: Color(hex: "E03A3E")),
        "sacramento kings":       .init(abbr: "SAC", color: Color(hex: "5A2D81")),
        "san antonio spurs":      .init(abbr: "SAS", color: Color(hex: "1A1A1A")),
        "toronto raptors":        .init(abbr: "TOR", color: Color(hex: "CE1141")),
        "utah jazz":              .init(abbr: "UTA", color: Color(hex: "002B5C")),
        "washington wizards":     .init(abbr: "WAS", color: Color(hex: "002B5C")),
    ]

    private static let mlb: [String: TeamStyle] = [
        "arizona diamondbacks":   .init(abbr: "ARI", color: Color(hex: "A71930")),
        "atlanta braves":         .init(abbr: "ATL", color: Color(hex: "CE1141")),
        "baltimore orioles":      .init(abbr: "BAL", color: Color(hex: "DF4601")),
        "boston red sox":         .init(abbr: "BOS", color: Color(hex: "BD3039")),
        "chicago cubs":           .init(abbr: "CHC", color: Color(hex: "0E3386")),
        "chicago white sox":      .init(abbr: "CHW", color: Color(hex: "27251F")),
        "cincinnati reds":        .init(abbr: "CIN", color: Color(hex: "C6011F")),
        "cleveland guardians":    .init(abbr: "CLE", color: Color(hex: "00385D")),
        "colorado rockies":       .init(abbr: "COL", color: Color(hex: "333366")),
        "detroit tigers":         .init(abbr: "DET", color: Color(hex: "0C2340")),
        "houston astros":         .init(abbr: "HOU", color: Color(hex: "002D62")),
        "kansas city royals":     .init(abbr: "KC",  color: Color(hex: "004687")),
        "los angeles angels":     .init(abbr: "LAA", color: Color(hex: "BA0021")),
        "los angeles dodgers":    .init(abbr: "LAD", color: Color(hex: "005A9C")),
        "miami marlins":          .init(abbr: "MIA", color: Color(hex: "00A3E0")),
        "milwaukee brewers":      .init(abbr: "MIL", color: Color(hex: "12284B")),
        "minnesota twins":        .init(abbr: "MIN", color: Color(hex: "002B5C")),
        "new york mets":          .init(abbr: "NYM", color: Color(hex: "002D72")),
        "new york yankees":       .init(abbr: "NYY", color: Color(hex: "003087")),
        "oakland athletics":      .init(abbr: "OAK", color: Color(hex: "003831")),
        "athletics":              .init(abbr: "ATH", color: Color(hex: "003831")),
        "philadelphia phillies":  .init(abbr: "PHI", color: Color(hex: "E81828")),
        "pittsburgh pirates":     .init(abbr: "PIT", color: Color(hex: "27251F")),
        "san diego padres":       .init(abbr: "SD",  color: Color(hex: "2F241D")),
        "san francisco giants":   .init(abbr: "SF",  color: Color(hex: "FD5A1E")),
        "seattle mariners":       .init(abbr: "SEA", color: Color(hex: "0C2C56")),
        "st. louis cardinals":    .init(abbr: "STL", color: Color(hex: "C41E3A")),
        "st louis cardinals":     .init(abbr: "STL", color: Color(hex: "C41E3A")),
        "tampa bay rays":         .init(abbr: "TB",  color: Color(hex: "092C5C")),
        "texas rangers":          .init(abbr: "TEX", color: Color(hex: "003278")),
        "toronto blue jays":      .init(abbr: "TOR", color: Color(hex: "134A8E")),
        "washington nationals":   .init(abbr: "WAS", color: Color(hex: "AB0003")),
    ]
}

extension TeamStyle {
    static func nickname(for team: String, league: String) -> String {
        let key = team.lowercased().trimmingCharacters(in: .whitespaces)
        if league.uppercased() == "MLB", let n = mlbNicknames[key] { return n }
        if league.uppercased() == "NBA", let n = nbaNicknames[key] { return n }
        return team.split(separator: " ").last.map(String.init) ?? team
    }

    private static let nbaNicknames: [String: String] = [
        "atlanta hawks": "Hawks", "boston celtics": "Celtics", "brooklyn nets": "Nets",
        "charlotte hornets": "Hornets", "chicago bulls": "Bulls", "cleveland cavaliers": "Cavaliers",
        "dallas mavericks": "Mavericks", "denver nuggets": "Nuggets", "detroit pistons": "Pistons",
        "golden state warriors": "Warriors", "houston rockets": "Rockets", "indiana pacers": "Pacers",
        "la clippers": "Clippers", "los angeles clippers": "Clippers", "los angeles lakers": "Lakers",
        "memphis grizzlies": "Grizzlies", "miami heat": "Heat", "milwaukee bucks": "Bucks",
        "minnesota timberwolves": "Timberwolves", "new orleans pelicans": "Pelicans",
        "new york knicks": "Knicks", "oklahoma city thunder": "Thunder", "orlando magic": "Magic",
        "philadelphia 76ers": "76ers", "phoenix suns": "Suns",
        "portland trail blazers": "Trail Blazers", "sacramento kings": "Kings",
        "san antonio spurs": "Spurs", "toronto raptors": "Raptors", "utah jazz": "Jazz",
        "washington wizards": "Wizards",
    ]

    private static let mlbNicknames: [String: String] = [
        "arizona diamondbacks": "Diamondbacks", "atlanta braves": "Braves",
        "baltimore orioles": "Orioles", "boston red sox": "Red Sox",
        "chicago cubs": "Cubs", "chicago white sox": "White Sox",
        "cincinnati reds": "Reds", "cleveland guardians": "Guardians",
        "colorado rockies": "Rockies", "detroit tigers": "Tigers",
        "houston astros": "Astros", "kansas city royals": "Royals",
        "los angeles angels": "Angels", "los angeles dodgers": "Dodgers",
        "miami marlins": "Marlins", "milwaukee brewers": "Brewers",
        "minnesota twins": "Twins", "new york mets": "Mets",
        "new york yankees": "Yankees", "oakland athletics": "Athletics", "athletics": "Athletics",
        "philadelphia phillies": "Phillies", "pittsburgh pirates": "Pirates",
        "san diego padres": "Padres", "san francisco giants": "Giants",
        "seattle mariners": "Mariners", "st. louis cardinals": "Cardinals",
        "st louis cardinals": "Cardinals", "tampa bay rays": "Rays",
        "texas rangers": "Rangers", "toronto blue jays": "Blue Jays",
        "washington nationals": "Nationals",
    ]
}

struct TeamBadge: View {
    let team: String
    let league: String
    var size: CGFloat = 30

    var body: some View {
        let style = TeamStyle.lookup(team, league: league)
        Text(style.abbr)
            .font(.system(size: size * 0.34, weight: .bold, design: .rounded))
            .foregroundColor(.white)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
            .frame(width: size, height: size)
            .background(
                Circle()
                    .fill(style.color)
                    .overlay(Circle().strokeBorder(Color.white.opacity(0.08), lineWidth: 1))
            )
    }
}

struct LiveGameCard: View {
    let game: TodayGame
    var awayInsight: TeamInsight? = nil
    var homeInsight: TeamInsight? = nil
    var onSelectMatchup: () -> Void = {}

    private var statusLabel: String {
        switch game.game_status {
        case 2: return "Live now"
        case 3: return "Final"
        default: return "Today"
        }
    }

    private var isLive: Bool { game.game_status == 2 }

    private var headline: String {
        let away = TeamStyle.nickname(for: game.away_team_full, league: "NBA")
        let home = TeamStyle.nickname(for: game.home_team_full, league: "NBA")
        return "\(away) @ \(home)"
    }

    private var totalInjuries: Int {
        (awayInsight?.injuryCount ?? 0) + (homeInsight?.injuryCount ?? 0)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Button(action: onSelectMatchup) {
                VStack(alignment: .leading, spacing: 14) {
                    SourceHeader(
                        leagueAbbr: "NBA",
                        leagueColor: .feedNBA,
                        label: isLive ? "NBA · Live" : "NBA Today",
                        timestamp: statusLabel
                    )

                    Text(headline)
                        .font(.system(size: 26, weight: .heavy, design: .serif))
                        .foregroundColor(.feedText)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)

                    VStack(spacing: 10) {
                        teamRow(team: game.away_team_full, insight: awayInsight)
                        teamRow(team: game.home_team_full, insight: homeInsight)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            HStack(spacing: 10) {
                if totalInjuries > 0 {
                    NavigationLink {
                        InjuryListView(
                            awayTeam: game.away_team_full,
                            homeTeam: game.home_team_full,
                            league: .NBA
                        )
                    } label: {
                        HStack(spacing: 5) {
                            Image(systemName: "cross.case.fill").font(.system(size: 11, weight: .semibold))
                            Text("\(totalInjuries) listed injuries").font(.system(size: 13, weight: .semibold))
                            Image(systemName: "chevron.right").font(.system(size: 10, weight: .bold))
                        }
                        .foregroundColor(.feedSub)
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
                Button(action: onSelectMatchup) {
                    FeedChip(icon: "chart.bar.fill", text: "Predict")
                }
                .buttonStyle(.plain)
            }
            .padding(.top, 2)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .feedCard()
    }

    @ViewBuilder
    private func teamRow(team: String, insight: TeamInsight?) -> some View {
        HStack(spacing: 12) {
            TeamBadge(team: team, league: "NBA", size: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(team)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.feedText)
                    .lineLimit(1)
                if let top = insight?.topScorer {
                    Text("\(top.player) · \(String(format: "%.1f", top.avg_points)) PPG")
                        .font(.system(size: 13))
                        .foregroundColor(.feedSub)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 0)
        }
    }
}

struct FeedResultCard: View {
    let game: Game
    var recent: [Game] = []

    private var homeWon: Bool { game.home_score > game.away_score }
    private var winner: String { homeWon ? game.home_team : game.away_team }
    private var loser:  String { homeWon ? game.away_team : game.home_team }
    private var winScore: Int { max(game.home_score, game.away_score) }
    private var loseScore: Int { min(game.home_score, game.away_score) }
    private var leagueColor: Color { game.league == "MLB" ? .feedMLB : .feedNBA }
    private var margin: Int { abs(game.home_score - game.away_score) }

    private var blowoutThreshold: Int { game.league == "MLB" ? 6 : 15 }
    private var closeThreshold: Int { game.league == "MLB" ? 2 : 5 }

    private var headline: String {
        let w = TeamStyle.nickname(for: winner, league: game.league)
        let l = TeamStyle.nickname(for: loser, league: game.league)
        return "\(w) beat \(l) \(winScore)–\(loseScore)"
    }

    private var subtitle: String {
        var parts: [String] = []

        if margin >= blowoutThreshold {
            parts.append("Dominant \(margin)-\(game.league == "MLB" ? "run" : "point") win")
        } else if margin <= closeThreshold {
            parts.append("Tight \(margin)-\(game.league == "MLB" ? "run" : "point") finish")
        } else {
            parts.append("\(winner) wins by \(margin)")
        }

        if let streak = winnerStreak(), streak >= 2 {
            parts.append("\(streak)-game win streak")
        }

        return parts.joined(separator: "  ·  ")
    }

    private func winnerStreak() -> Int? {
        let games = recent
            .filter { $0.league == game.league }
            .sorted { $0.date > $1.date }
        var streak = 0
        for g in games where g.date <= game.date {
            let w = g.home_score > g.away_score ? g.home_team : g.away_team
            if w == winner { streak += 1 } else { break }
        }
        return streak
    }

    private var formattedDate: String {
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        guard let d = inFmt.date(from: game.date) else { return game.date }
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: d), to: Calendar.current.startOfDay(for: Date())).day ?? 0
        switch days {
        case 0: return "Today"
        case 1: return "Yesterday"
        case 2...6: return "\(days)d ago"
        default:
            let out = DateFormatter()
            out.dateFormat = "MMM d"
            return out.string(from: d)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SourceHeader(
                leagueAbbr: game.league,
                leagueColor: leagueColor,
                label: "\(game.league) · Final",
                timestamp: formattedDate
            )

            Text(headline)
                .font(.system(size: 26, weight: .heavy, design: .serif))
                .foregroundColor(.feedText)
                .lineLimit(1)
                .minimumScaleFactor(0.65)

            VStack(spacing: 10) {
                resultRow(team: game.away_team, score: game.away_score, won: !homeWon)
                resultRow(team: game.home_team, score: game.home_score, won: homeWon)
            }

            Text(subtitle)
                .font(.system(size: 14))
                .foregroundColor(.feedSub)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            HStack {
                Spacer()
                FeedChip(icon: "chart.line.uptrend.xyaxis", text: "Details")
            }
            .padding(.top, 2)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .feedCard()
    }

    @ViewBuilder
    private func resultRow(team: String, score: Int, won: Bool) -> some View {
        HStack(spacing: 12) {
            TeamBadge(team: team, league: game.league, size: 30)
                .opacity(won ? 1.0 : 0.55)
            Text(team)
                .font(.system(size: 15, weight: won ? .semibold : .regular))
                .foregroundColor(won ? .feedText : .feedSub)
                .lineLimit(1)
            Spacer(minLength: 0)
            Text("\(score)")
                .font(.system(size: 20, weight: won ? .bold : .regular, design: .rounded))
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

    private var leagueAbbr: String { accent == Color.feedMLB ? "MLB" : "NBA" }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SourceHeader(
                leagueAbbr: leagueAbbr,
                leagueColor: accent,
                label: "\(leagueAbbr) · Top performer",
                timestamp: subtitle
            )

            Text(name)
                .font(.system(size: 22, weight: .heavy, design: .serif))
                .foregroundColor(.feedText)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            stats()
                .padding(.top, 2)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
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

// MARK: - Injury detail view

struct InjuryListView: View {
    let awayTeam: String
    let homeTeam: String
    let league: Sport

    @State private var awayInjuries: [Injury] = []
    @State private var homeInjuries: [Injury] = []
    @State private var loading = true
    @State private var error = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                matchupHeader

                if loading {
                    HStack { Spacer(); ProgressView().tint(.feedNBA); Spacer() }
                        .padding(.top, 60)
                } else if !error.isEmpty {
                    Text(error)
                        .font(.system(size: 14))
                        .foregroundColor(.feedLive)
                        .padding(.top, 20)
                } else if awayInjuries.isEmpty && homeInjuries.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "checkmark.seal.fill")
                            .font(.system(size: 44))
                            .foregroundColor(Color(hex: "16a34a"))
                        Text("No injuries reported")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundColor(.feedText)
                        Text("Both teams are clean")
                            .font(.system(size: 13))
                            .foregroundColor(.feedSub)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 50)
                } else {
                    teamSection(team: awayTeam, injuries: awayInjuries)
                    teamSection(team: homeTeam, injuries: homeInjuries)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
        }
        .background(Color.feedBg.ignoresSafeArea())
        .navigationTitle("Injury Report")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.feedBg, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .preferredColorScheme(.light)
        .task { await load() }
    }

    private var matchupHeader: some View {
        HStack(spacing: 10) {
            TeamBadge(team: awayTeam, league: league.rawValue, size: 34)
            Text(TeamStyle.nickname(for: awayTeam, league: league.rawValue))
                .font(.system(size: 18, weight: .heavy, design: .serif))
                .foregroundColor(.feedText)
            Text("@")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.feedSub)
            Text(TeamStyle.nickname(for: homeTeam, league: league.rawValue))
                .font(.system(size: 18, weight: .heavy, design: .serif))
                .foregroundColor(.feedText)
            TeamBadge(team: homeTeam, league: league.rawValue, size: 34)
            Spacer(minLength: 0)
        }
        .padding(.bottom, 4)
    }

    @ViewBuilder
    private func teamSection(team: String, injuries: [Injury]) -> some View {
        if !injuries.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 10) {
                    TeamBadge(team: team, league: league.rawValue, size: 28)
                    Text(team)
                        .font(.system(size: 17, weight: .bold))
                        .foregroundColor(.feedText)
                    Spacer()
                    Text("\(injuries.count)")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.feedSub)
                        .padding(.horizontal, 9).padding(.vertical, 3)
                        .background(Color.feedChip)
                        .clipShape(Capsule())
                }

                VStack(spacing: 8) {
                    ForEach(injuries) { InjuryRow(injury: $0) }
                }
            }
            .padding(.top, 6)
        }
    }

    private func load() async {
        loading = true
        error = ""
        async let away = API.injuries(league: league, team: awayTeam)
        async let home = API.injuries(league: league, team: homeTeam)
        self.awayInjuries = (try? await away) ?? []
        self.homeInjuries = (try? await home) ?? []
        loading = false
    }
}

struct InjuryRow: View {
    let injury: Injury

    private var statusColor: Color {
        switch injury.status.lowercased() {
        case "out":                        return .feedLive
        case "doubtful":                   return Color(hex: "ea580c")
        case "questionable", "day-to-day": return Color(hex: "ca8a04")
        default:                           return .feedSub
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(injury.player_name)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.feedText)
                Spacer()
                Text(injury.status.uppercased())
                    .font(.system(size: 10, weight: .heavy))
                    .kerning(0.6)
                    .foregroundColor(statusColor)
                    .padding(.horizontal, 9).padding(.vertical, 4)
                    .background(statusColor.opacity(0.14))
                    .clipShape(Capsule())
            }

            let desc = injury.injuryDescription
            if !desc.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "bandage.fill")
                        .font(.system(size: 11))
                        .foregroundColor(.feedSub)
                    Text(desc.capitalized)
                        .font(.system(size: 13))
                        .foregroundColor(.feedSub)
                }
            }

            if let ret = injury.return_date, !ret.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "calendar")
                        .font(.system(size: 11))
                        .foregroundColor(.feedSub)
                    Text("Expected back: \(ret)")
                        .font(.system(size: 13))
                        .foregroundColor(.feedSub)
                }
            }

            if let note = injury.short_comment, !note.isEmpty {
                Text(note)
                    .font(.system(size: 13))
                    .foregroundColor(.feedText.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
            } else if let long = injury.long_comment, !long.isEmpty {
                Text(long)
                    .font(.system(size: 13))
                    .foregroundColor(.feedText.opacity(0.85))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Spacer()
                Text("Updated \(injury.last_updated)")
                    .font(.system(size: 10))
                    .foregroundColor(.feedSub.opacity(0.8))
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.feedCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

#Preview {
    HomeView()
        .environmentObject(AppState())
}
