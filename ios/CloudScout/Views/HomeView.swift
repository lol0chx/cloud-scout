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
    @State private var nbaInjuryFeed: [TeamInjurySummary] = []
    @State private var mlbInjuryFeed: [TeamInjurySummary] = []
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.csBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    feedHeader
                        .padding(.horizontal, 18)
                        .padding(.top, 4)
                        .padding(.bottom, 14)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.csLive).padding()
                    } else if loading && nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer(); ProgressView().tint(.csNBA); Spacer()
                    } else if nbaGames.isEmpty && mlbGames.isEmpty {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "chart.line.uptrend").font(.system(size: 40)).foregroundColor(.csBorder)
                            Text("No games yet").font(.system(size: 16, weight: .semibold)).foregroundColor(.csSub)
                            Text("Go to Update tab to scrape data").font(.system(size: 13)).foregroundColor(.csBorder)
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
                                                sport: game.sport,
                                                homeTeam: game.home_team_full,
                                                awayTeam: game.away_team_full
                                            )
                                            state.sport = game.sport
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

                                ForEach(nbaInjuryFeed.prefix(2)) { summary in
                                    NavigationLink {
                                        InjuryListView(awayTeam: summary.team, league: .NBA)
                                    } label: {
                                        InjuryFeedCard(summary: summary, league: .NBA)
                                    }
                                    .buttonStyle(.plain)
                                }

                                if !mlbGames.isEmpty || mlbTopPerformers != nil {
                                    MLBSectionDivider()
                                        .padding(.vertical, 2)
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

                                ForEach(mlbInjuryFeed.prefix(2)) { summary in
                                    NavigationLink {
                                        InjuryListView(awayTeam: summary.team, league: .MLB)
                                    } label: {
                                        InjuryFeedCard(summary: summary, league: .MLB)
                                    }
                                    .buttonStyle(.plain)
                                }

                                Spacer(minLength: 20)
                            }
                            .padding(.horizontal, 16)
                        }
                    }
                }
            }
            .toolbarBackground(Color.csBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { await loadAll() }
    }

    private var feedHeader: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 2) {
                Text(eyebrowDay.uppercased())
                    .font(.csSection)
                    .kerning(1.0)
                    .foregroundColor(.csSub)
                Text("Feed")
                    .font(.csEditorial(40))
                    .foregroundColor(.csText)
            }
            Spacer()
            HStack(spacing: 10) {
                Button { Task { await loadAll() } } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(.csNBA)
                        .frame(width: 36, height: 36)
                        .background(Color.csCard)
                        .clipShape(Circle())
                        .overlay(Circle().strokeBorder(Color.csBorder, lineWidth: 1))
                }
                avatarChip
            }
        }
    }

    private var avatarChip: some View {
        ZStack {
            Circle().fill(Color.csNBA.opacity(0.18))
            Image(systemName: "person.fill")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(.csNBA)
        }
        .frame(width: 36, height: 36)
        .overlay(Circle().strokeBorder(Color.csBorder, lineWidth: 1))
    }

    private var eyebrowDay: String {
        let f = DateFormatter()
        f.dateFormat = "EEEE, MMM d"
        return f.string(from: Date())
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
        await loadInjuryFeeds()
    }

    private func loadInjuryFeeds() async {
        async let nba = API.injuries(league: .NBA)
        async let mlb = API.injuries(league: .MLB)
        let nbaList = (try? await nba) ?? []
        let mlbList = (try? await mlb) ?? []
        self.nbaInjuryFeed = Array(makeInjuryFeed(from: nbaList).prefix(2))
        self.mlbInjuryFeed = Array(makeInjuryFeed(from: mlbList).prefix(2))
    }

    private func makeInjuryFeed(from list: [Injury]) -> [TeamInjurySummary] {
        Dictionary(grouping: list, by: { $0.team }).map { team, items in
            let sorted = items.sorted { rankInjury($0.status) < rankInjury($1.status) }
            let outCount = items.filter { $0.status.lowercased() == "out" }.count
            return TeamInjurySummary(team: team, count: items.count, topPlayers: sorted, outCount: outCount)
        }
        .sorted {
            if $0.outCount != $1.outCount { return $0.outCount > $1.outCount }
            return $0.count > $1.count
        }
    }

    private func rankInjury(_ status: String) -> Int {
        switch status.lowercased() {
        case "out": return 0
        case "doubtful": return 1
        case "questionable", "day-to-day": return 2
        default: return 3
        }
    }

    private func loadTeamInsights() async {
        // One (team → sport) entry per team in any of today's games, both
        // leagues. Team names don't collide across NBA/MLB so a single dict
        // keyed by full name is safe.
        var pairs: [String: Sport] = [:]
        for g in todayGames {
            pairs[g.home_team_full] = g.sport
            pairs[g.away_team_full] = g.sport
        }
        guard !pairs.isEmpty else { return }

        await withTaskGroup(of: (String, TeamInsight?).self) { group in
            for (team, sport) in pairs {
                group.addTask {
                    async let perf = API.topPerformers(league: sport, team: team, n: 15)
                    async let inj  = API.injuries(league: sport, team: team)
                    let resp = try? await perf
                    let topLine: String?
                    switch sport {
                    case .NBA:
                        if let p = resp?.players?.max(by: { $0.avg_points < $1.avg_points }) {
                            topLine = "\(p.player) · \(String(format: "%.1f", p.avg_points)) PPG"
                        } else { topLine = nil }
                    case .MLB:
                        if let b = resp?.batters?.max(by: { $0.HR < $1.HR }) {
                            if b.HR > 0 {
                                topLine = "\(b.player) · \(b.HR) HR"
                            } else {
                                let avg = String(format: "%.3f", b.AVG)
                                    .replacingOccurrences(of: "0.", with: ".")
                                topLine = "\(b.player) · \(avg) AVG"
                            }
                        } else { topLine = nil }
                    }
                    let injured = (try? await inj)?.filter {
                        let s = $0.status.lowercased()
                        switch sport {
                        case .NBA:
                            return s == "out" || s == "doubtful" || s == "questionable"
                        case .MLB:
                            // MLB uses IL tiers / day-to-day, not the NBA labels.
                            return s.contains("il") || s.contains("out")
                                || s.contains("day-to-day")
                        }
                    } ?? []
                    return (team, TeamInsight(topLine: topLine, injuryCount: injured.count))
                }
            }
            for await (team, insight) in group {
                if let insight { teamInsight[team] = insight }
            }
        }
    }
}

struct TeamInsight {
    let topLine: String?
    let injuryCount: Int
}

struct TeamInjurySummary: Identifiable {
    var id: String { team }
    let team: String
    let count: Int
    let topPlayers: [Injury]
    let outCount: Int
}

struct InjuryFeedCard: View {
    let summary: TeamInjurySummary
    let league: Sport

    private var leagueColor: Color { league == .NBA ? .csNBA : .csMLB }

    private var headline: String {
        let nick = TeamStyle.nickname(for: summary.team, league: league.rawValue)
        if summary.outCount > 0 {
            return "\(nick) shorthanded with \(summary.outCount) out"
        }
        return "\(nick) carry \(summary.count) listed injuries"
    }

    private func statusKind(_ status: String) -> StatusPill.Kind? {
        switch status.lowercased() {
        case "out": return .out
        case "doubtful": return .doubtful
        case "questionable", "day-to-day": return .questionable
        default: return nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SourceHeader(
                leagueAbbr: league.rawValue,
                leagueColor: leagueColor,
                label: "Injury Report",
                timestamp: "\(summary.count) listed",
                showsMenu: false
            )

            HStack(alignment: .top, spacing: 12) {
                TeamBadge(team: summary.team, league: league.rawValue, size: 36)
                Text(headline)
                    .font(.csEditorial(24))
                    .foregroundColor(.csText)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }

            VStack(spacing: 6) {
                ForEach(summary.topPlayers.prefix(3)) { inj in
                    HStack(spacing: 10) {
                        Text(inj.player_name)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(.csText)
                            .lineLimit(1)
                        Spacer(minLength: 8)
                        if let kind = statusKind(inj.status) {
                            StatusPill(kind: kind, text: inj.status)
                        } else {
                            Text(inj.status.uppercased())
                                .font(.system(size: 10, weight: .heavy))
                                .kerning(0.5)
                                .foregroundColor(.csSub)
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Color.csChip)
                                .clipShape(Capsule())
                        }
                    }
                }
            }

            HStack {
                Spacer()
                Chip(icon: "cross.case.fill", text: "Full report")
            }
            .padding(.top, 2)
        }
        .csCard(radius: 18)
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

// MARK: - Section divider (MLB)

struct MLBSectionDivider: View {
    var body: some View {
        HStack(spacing: 12) {
            Rectangle().fill(Color.csBorder).frame(height: 1)
            Text("MLB")
                .font(.csSection)
                .kerning(1.4)
                .foregroundColor(.csMLB)
            Rectangle().fill(Color.csBorder).frame(height: 1)
        }
        .padding(.vertical, 6)
    }
}

struct LiveGameCard: View {
    let game: TodayGame
    var awayInsight: TeamInsight? = nil
    var homeInsight: TeamInsight? = nil
    var onSelectMatchup: () -> Void = {}

    private static let isoDateFmt: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    private static let prettyDateFmt: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US")
        f.dateFormat = "EEE, MMM d"   // e.g. "Mon, May 18"
        return f
    }()

    // Scheduled games: show the real game date (known even when tip-off is
    // "TBD") instead of a blanket "Today" that was wrong for future games.
    private static func scheduledLabel(_ date: String?) -> String {
        guard let s = date, let d = isoDateFmt.date(from: s) else { return "Scheduled" }
        if Calendar.current.isDateInToday(d) { return "Today" }
        if Calendar.current.isDateInTomorrow(d) { return "Tomorrow" }
        return prettyDateFmt.string(from: d)
    }

    private var statusLabel: String {
        switch game.game_status {
        case 2: return "Live now"
        case 3: return "Final"
        default: return Self.scheduledLabel(game.date)
        }
    }

    private var isLive: Bool { game.game_status == 2 }

    private var sport: Sport { game.sport }
    private var leagueName: String { game.leagueName }
    private var leagueColor: Color { sport == .MLB ? .csMLB : .csNBA }

    private var headline: String {
        let away = TeamStyle.nickname(for: game.away_team_full, league: leagueName)
        let home = TeamStyle.nickname(for: game.home_team_full, league: leagueName)
        return "\(away) @ \(home)"
    }

    private var totalInjuries: Int {
        (awayInsight?.injuryCount ?? 0) + (homeInsight?.injuryCount ?? 0)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Button(action: onSelectMatchup) {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        SourceHeader(
                            leagueAbbr: leagueName,
                            leagueColor: leagueColor,
                            label: "\(leagueName) Today",
                            timestamp: statusLabel,
                            showsMenu: false
                        )
                        if isLive {
                            StatusPill(kind: .live, text: "Live")
                        }
                    }

                    Text(headline)
                        .font(.csEditorial(28))
                        .foregroundColor(.csText)
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
                            league: sport
                        )
                    } label: {
                        Chip(icon: "cross.case.fill", text: "\(totalInjuries) listed injuries")
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
                Button(action: onSelectMatchup) {
                    Chip(icon: "chart.bar.fill", text: "Predict", foreground: leagueColor)
                }
                .buttonStyle(.plain)
            }
            .padding(.top, 2)
        }
        .csCard(radius: 18)
    }

    @ViewBuilder
    private func teamRow(team: String, insight: TeamInsight?) -> some View {
        HStack(spacing: 12) {
            TeamBadge(team: team, league: leagueName, size: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(team)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.csText)
                    .lineLimit(1)
                if let line = insight?.topLine {
                    Text(line)
                        .font(.system(size: 13))
                        .foregroundColor(.csSub)
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
    private var leagueColor: Color { game.league == "MLB" ? .csMLB : .csNBA }
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
            HStack(spacing: 10) {
                SourceHeader(
                    leagueAbbr: game.league,
                    leagueColor: leagueColor,
                    label: game.league,
                    timestamp: formattedDate,
                    showsMenu: false
                )
                StatusPill(kind: .final, text: "Final")
            }

            Text(headline)
                .font(.csEditorial(28))
                .foregroundColor(.csText)
                .lineLimit(1)
                .minimumScaleFactor(0.65)

            VStack(spacing: 10) {
                resultRow(team: game.away_team, score: game.away_score, won: !homeWon)
                resultRow(team: game.home_team, score: game.home_score, won: homeWon)
            }

            Text(subtitle)
                .font(.system(size: 14))
                .foregroundColor(.csSub)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            HStack {
                Spacer()
                Chip(icon: "chart.line.uptrend.xyaxis", text: "Details")
            }
            .padding(.top, 2)
        }
        .csCard(radius: 18)
    }

    @ViewBuilder
    private func resultRow(team: String, score: Int, won: Bool) -> some View {
        HStack(spacing: 12) {
            TeamBadge(team: team, league: game.league, size: 30)
                .opacity(won ? 1.0 : 0.5)
            Text(team)
                .font(.system(size: 15, weight: won ? .semibold : .regular))
                .foregroundColor(won ? .csText : .csSub)
                .opacity(won ? 1.0 : 0.85)
                .lineLimit(1)
            Spacer(minLength: 0)
            Text("\(score)")
                .font(.csMono(22, weight: won ? .bold : .regular))
                .foregroundColor(won ? leagueColor : .csSub)
                .monospacedDigit()
        }
    }
}

struct NBAPerformerCard: View {
    let player: NBATopPlayer

    var body: some View {
        PlayerCardShell(
            name: player.player,
            subtitle: "\(player.games) GP · Top performer",
            accent: .csNBA
        ) {
            HStack(spacing: 8) {
                StatBox(value: String(format: "%.1f", player.avg_points), label: "PTS")
                StatBox(value: String(format: "%.1f", player.avg_assists), label: "AST")
                StatBox(value: String(format: "%.1f", player.avg_rebounds), label: "REB")
                StatBox(value: "\(player.games)", label: "GP")
            }
        }
    }
}

struct MLBBatterCard: View {
    let batter: MLBBatter

    var body: some View {
        PlayerCardShell(
            name: batter.player,
            subtitle: "\(batter.games) G · Batter",
            accent: .csMLB
        ) {
            HStack(spacing: 8) {
                StatBox(value: String(format: "%.3f", batter.AVG), label: "AVG")
                StatBox(value: "\(batter.HR)", label: "HR")
                StatBox(value: "\(batter.RBI)", label: "RBI")
                StatBox(value: "\(batter.games)", label: "G")
            }
        }
    }
}

struct MLBPitcherCard: View {
    let pitcher: MLBPitcher

    var body: some View {
        PlayerCardShell(
            name: pitcher.player,
            subtitle: "\(pitcher.games) G · Pitcher",
            accent: .csMLB
        ) {
            HStack(spacing: 8) {
                StatBox(value: String(format: "%.2f", pitcher.ERA), label: "ERA")
                StatBox(value: String(format: "%.2f", pitcher.WHIP), label: "WHIP")
                StatBox(value: "\(pitcher.SO)", label: "K")
                StatBox(value: "\(pitcher.games)", label: "G")
            }
        }
    }
}

struct PlayerCardShell<Stats: View>: View {
    let name: String
    let subtitle: String
    let accent: Color
    @ViewBuilder let stats: () -> Stats

    private var league: String { accent == Color.csMLB ? "MLB" : "NBA" }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SourceHeader(
                leagueAbbr: league,
                leagueColor: accent,
                label: "\(league) · Top performer",
                timestamp: subtitle,
                showsMenu: false
            )

            Text(name)
                .font(.csEditorial(26))
                .foregroundColor(.csText)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            stats()
                .padding(.top, 2)
        }
        .csCard(radius: 18)
    }
}

// MARK: - Injury detail view

struct InjuryListView: View {
    let awayTeam: String
    let homeTeam: String?
    let league: Sport

    init(awayTeam: String, homeTeam: String? = nil, league: Sport) {
        self.awayTeam = awayTeam
        self.homeTeam = homeTeam
        self.league = league
    }

    @State private var awayInjuries: [Injury] = []
    @State private var homeInjuries: [Injury] = []
    @State private var loading = true
    @State private var error = ""

    private var allInjuries: [Injury] { awayInjuries + homeInjuries }
    private var outCount: Int { allInjuries.filter { $0.status.lowercased() == "out" }.count }
    private var doubtfulCount: Int { allInjuries.filter { $0.status.lowercased() == "doubtful" }.count }
    private var questionableCount: Int {
        allInjuries.filter { let s = $0.status.lowercased(); return s == "questionable" || s == "day-to-day" }.count
    }

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 14) {
                matchupHeader
                    .padding(.horizontal, 20)
                    .padding(.top, 6)

                if loading {
                    HStack { Spacer(); ProgressView().tint(.csNBA); Spacer() }
                        .padding(.top, 60)
                } else if !error.isEmpty {
                    Text(error)
                        .font(.system(size: 14))
                        .foregroundColor(.csLive)
                        .padding(.horizontal, 16)
                        .padding(.top, 20)
                } else if allInjuries.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "checkmark.seal.fill")
                            .font(.system(size: 44))
                            .foregroundColor(.csWin)
                        Text("No injuries reported")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundColor(.csText)
                        Text("Both teams are clean")
                            .font(.system(size: 13))
                            .foregroundColor(.csSub)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 50)
                } else {
                    summaryStrip
                        .padding(.horizontal, 14)

                    teamSection(team: awayTeam, injuries: awayInjuries)
                    if let homeTeam {
                        teamSection(team: homeTeam, injuries: homeInjuries)
                    }
                }

                Spacer(minLength: 30)
            }
            .padding(.bottom, 30)
        }
        .background(Color.csBg.ignoresSafeArea())
        .navigationTitle("Injury Report")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.csBg, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .preferredColorScheme(.light)
        .task { await load() }
    }

    @ViewBuilder
    private var matchupHeader: some View {
        if let homeTeam {
            HStack(spacing: 10) {
                Spacer(minLength: 0)
                TeamBadge(team: awayTeam, league: league.rawValue, size: 34)
                Text(TeamStyle.nickname(for: awayTeam, league: league.rawValue))
                    .font(.csEditorial(22))
                    .foregroundColor(.csText)
                Text("@")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.csSub)
                Text(TeamStyle.nickname(for: homeTeam, league: league.rawValue))
                    .font(.csEditorial(22))
                    .foregroundColor(.csText)
                TeamBadge(team: homeTeam, league: league.rawValue, size: 34)
                Spacer(minLength: 0)
            }
        } else {
            HStack(spacing: 10) {
                Spacer(minLength: 0)
                TeamBadge(team: awayTeam, league: league.rawValue, size: 40)
                Text(awayTeam)
                    .font(.csEditorial(24))
                    .foregroundColor(.csText)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Spacer(minLength: 0)
            }
        }
    }

    private var summaryStrip: some View {
        HStack(spacing: 0) {
            InjurySummary(value: allInjuries.count, label: "Total", color: .csText)
            Divider().background(Color.csBorder)
            InjurySummary(value: outCount, label: "Out", color: .csLoss)
            Divider().background(Color.csBorder)
            InjurySummary(value: doubtfulCount, label: "Doubtful", color: Color(hex: "ea580c"))
            Divider().background(Color.csBorder)
            InjurySummary(value: questionableCount, label: "Questionable", color: Color(hex: "ca8a04"))
        }
        .padding(.horizontal, 6).padding(.vertical, 12)
        .frame(maxWidth: .infinity)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    @ViewBuilder
    private func teamSection(team: String, injuries: [Injury]) -> some View {
        if !injuries.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                SectionHeader(title: team) {
                    Text("\(injuries.count)")
                        .font(.system(size: 11, weight: .heavy))
                        .foregroundColor(.csSub)
                        .padding(.horizontal, 9).padding(.vertical, 3)
                        .background(Color.csChip)
                        .clipShape(Capsule())
                }
                .padding(.horizontal, 16)

                VStack(spacing: 8) {
                    ForEach(injuries) { InjuryRow(injury: $0) }
                }
                .padding(.horizontal, 14)
            }
            .padding(.top, 4)
        }
    }

    private func load() async {
        loading = true
        error = ""
        async let away = API.injuries(league: league, team: awayTeam)
        self.awayInjuries = (try? await away) ?? []
        if let homeTeam {
            self.homeInjuries = (try? await API.injuries(league: league, team: homeTeam)) ?? []
        } else {
            self.homeInjuries = []
        }
        loading = false
    }
}

private struct InjurySummary: View {
    let value: Int
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text("\(value)")
                .font(.csMono(22, weight: .heavy))
                .foregroundColor(color)
                .monospacedDigit()
            Text(label)
                .font(.system(size: 10, weight: .semibold))
                .kerning(0.3)
                .foregroundColor(.csSub)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
    }
}

struct InjuryRow: View {
    let injury: Injury

    private var statusKind: StatusPill.Kind? {
        switch injury.status.lowercased() {
        case "out":                        return .out
        case "doubtful":                   return .doubtful
        case "questionable", "day-to-day": return .questionable
        default:                           return nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(injury.player_name)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.csText)
                Spacer()
                if let kind = statusKind {
                    StatusPill(kind: kind, text: injury.status)
                } else {
                    Text(injury.status.uppercased())
                        .font(.system(size: 10, weight: .heavy))
                        .kerning(0.6)
                        .foregroundColor(.csSub)
                        .padding(.horizontal, 9).padding(.vertical, 4)
                        .background(Color.csChip)
                        .clipShape(Capsule())
                }
            }

            let desc = injury.injuryDescription
            if !desc.isEmpty {
                Text(desc.capitalized)
                    .font(.system(size: 12))
                    .foregroundColor(.csSub)
            }

            if let ret = injury.return_date, !ret.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "calendar")
                        .font(.system(size: 11))
                        .foregroundColor(.csSub)
                    Text("Expected back: ")
                        .foregroundColor(.csSub)
                    + Text(ret)
                        .foregroundColor(.csText)
                        .fontWeight(.semibold)
                }
                .font(.system(size: 12))
            }

            if let note = injury.short_comment, !note.isEmpty {
                Text(note)
                    .font(.system(size: 12))
                    .foregroundColor(.csText)
                    .padding(.horizontal, 10).padding(.vertical, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.csChip)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else if let long = injury.long_comment, !long.isEmpty {
                Text(long)
                    .font(.system(size: 12))
                    .foregroundColor(.csText)
                    .lineLimit(3)
                    .padding(.horizontal, 10).padding(.vertical, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.csChip)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

#Preview {
    HomeView()
        .environmentObject(AppState())
}
