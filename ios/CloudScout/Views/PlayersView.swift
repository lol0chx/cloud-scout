import SwiftUI

struct PlayersView: View {
    @EnvironmentObject var state: AppState
    @State private var role: PlayerRole = .batter
    @State private var search = ""
    @State private var players: [String] = []
    @State private var selectedPlayer: String?
    @State private var topPerformers: TopPerformersResponse?
    @State private var topTeam = ""
    @State private var loadingTop = false
    @State private var loadingPlayers = false
    @State private var searchTask: Task<Void, Never>?
    @State private var teams: [String] = []

    enum PlayerRole: String, CaseIterable {
        case batter, pitcher
        var label: String { self == .batter ? "Batters" : "Pitchers" }
    }

    private var isMLB: Bool { state.sport == .MLB }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.csBg.ignoresSafeArea()
                if let player = selectedPlayer {
                    PlayerDetailView(
                        player: player,
                        sport: state.sport,
                        role: role.rawValue,
                        teams: teams,
                        teamContext: topTeam,
                        onBack: { selectedPlayer = nil }
                    )
                } else {
                    VStack(spacing: 0) {
                        header
                            .padding(.horizontal, 18)
                            .padding(.top, 4)
                            .padding(.bottom, 14)

                        VStack(spacing: 10) {
                            SportToggle(sport: $state.sport)
                            if isMLB { roleToggle }
                            searchField
                        }
                        .padding(.horizontal, 16)
                        .padding(.bottom, 10)

                        if loadingPlayers {
                            ProgressView().tint(.csNBA).padding(.bottom, 8)
                        }

                        if search.isEmpty {
                            ScrollView {
                                VStack(alignment: .leading, spacing: 16) {
                                    topPerformersSection
                                    allPlayersSection
                                    Spacer(minLength: 20)
                                }
                                .padding(.horizontal, 16)
                                .padding(.top, 4)
                            }
                        } else {
                            ScrollView {
                                LazyVStack(spacing: 0) {
                                    ForEach(Array(players.prefix(50).enumerated()), id: \.offset) { idx, name in
                                        Button { selectedPlayer = name } label: {
                                            AllPlayerRow(name: name)
                                        }
                                        .buttonStyle(.plain)
                                        if idx < min(players.count, 50) - 1 {
                                            Divider().background(Color.csBorder)
                                                .padding(.leading, 52)
                                        }
                                    }
                                }
                                .background(Color.csCard)
                                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                                .padding(.horizontal, 16)
                                .padding(.top, 4)
                                .padding(.bottom, 20)
                            }
                        }
                    }
                }
            }
            .toolbarBackground(Color.csBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { await setup() }
        .onChange(of: state.sport) { _, _ in Task { await setup() } }
        .onChange(of: role) { _, _ in Task { await loadPlayers(); await loadTop() } }
        .onChange(of: topTeam) { _, _ in Task { await loadTop() } }
        .onChange(of: search) { _, _ in
            searchTask?.cancel()
            searchTask = Task {
                try? await Task.sleep(nanoseconds: 300_000_000)
                if !Task.isCancelled { await loadPlayers() }
            }
        }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 2) {
                Text("ROSTER")
                    .font(.csSection)
                    .kerning(1.0)
                    .foregroundColor(.csSub)
                Text("Players")
                    .font(.csEditorial(40))
                    .foregroundColor(.csText)
            }
            Spacer()
        }
    }

    private var roleToggle: some View {
        HStack(spacing: 0) {
            ForEach(PlayerRole.allCases, id: \.self) { r in
                Button { role = r } label: {
                    Text(r.label)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(role == r ? .white : .csSub)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(role == r ? Color.csMLB : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Color.csChip)
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }

    private var searchField: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.csFaint)
            TextField("Search players…", text: $search)
                .textFieldStyle(.plain)
                .foregroundColor(.csText)
                .tint(.csNBA)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(Color.csBorder, lineWidth: 1))
    }

    @ViewBuilder
    private var topPerformersSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Top Performers") {
                if !teams.isEmpty {
                    Menu {
                        ForEach(teams, id: \.self) { t in
                            Button(t) { topTeam = t }
                        }
                    } label: {
                        HStack(spacing: 6) {
                            Text(topTeam.isEmpty ? "Select team" : topTeam)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(.csText)
                                .lineLimit(1)
                            Image(systemName: "chevron.down")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(.csSub)
                        }
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(Color.csChip)
                        .clipShape(Capsule())
                    }
                }
            }

            if loadingTop {
                HStack { Spacer(); ProgressView().tint(.csNBA); Spacer() }.padding(.top, 8)
            } else if let tp = topPerformers {
                VStack(spacing: 8) {
                    TopPerformersSection(tp: tp, isMLB: isMLB, role: role.rawValue, team: topTeam, league: state.sport.rawValue) { name in
                        selectedPlayer = name
                    }
                }
            }
        }
    }

    private var allPlayersSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "All Players")
            LazyVStack(spacing: 0) {
                ForEach(Array(players.prefix(50).enumerated()), id: \.offset) { idx, name in
                    Button { selectedPlayer = name } label: {
                        AllPlayerRow(name: name)
                    }
                    .buttonStyle(.plain)
                    if idx < min(players.count, 50) - 1 {
                        Divider().background(Color.csBorder)
                            .padding(.leading, 52)
                    }
                }
            }
            .background(Color.csCard)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }

    private func setup() async {
        selectedPlayer = nil; search = ""
        async let t = API.teams(league: state.sport)
        async let p = API.players(league: state.sport, name: "", role: isMLB ? role.rawValue : "")
        do {
            teams = try await t
            players = try await p
            if let first = teams.first { topTeam = first }
        } catch {}
        await loadTop()
    }

    private func loadPlayers() async {
        loadingPlayers = true
        do { players = try await API.players(league: state.sport, name: search, role: isMLB ? role.rawValue : "") }
        catch { players = [] }
        loadingPlayers = false
    }

    private func loadTop() async {
        guard !topTeam.isEmpty else { return }
        loadingTop = true
        do { topPerformers = try await API.topPerformers(league: state.sport, team: topTeam) }
        catch { topPerformers = nil }
        loadingTop = false
    }
}

// MARK: - Rows

private struct AllPlayerRow: View {
    let name: String

    private var initials: String {
        let parts = name.split(separator: " ")
        let letters = parts.prefix(2).compactMap { $0.first.map(String.init) }.joined()
        return letters.isEmpty ? "?" : letters.uppercased()
    }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle().fill(Color.csChip)
                Text(initials)
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.csSub)
            }
            .frame(width: 32, height: 32)
            Text(name).font(.system(size: 15, weight: .medium)).foregroundColor(.csText)
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .bold)).foregroundColor(.csFaint)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .contentShape(Rectangle())
    }
}

private struct TopPerformersSection: View {
    let tp: TopPerformersResponse
    let isMLB: Bool
    let role: String
    let team: String
    let league: String
    let onSelect: (String) -> Void

    var body: some View {
        VStack(spacing: 8) {
            if let players = tp.players {
                ForEach(players) { p in
                    TopPlayerRow(
                        name: p.player,
                        team: team,
                        league: league,
                        stats: [
                            ("PTS", String(format: "%.1f", p.avg_points)),
                            ("AST", String(format: "%.1f", p.avg_assists)),
                            ("REB", String(format: "%.1f", p.avg_rebounds)),
                            ("GP",  "\(p.games)"),
                        ],
                        onTap: { onSelect(p.player) }
                    )
                }
            }
            if let batters = tp.batters, role == "batter" {
                ForEach(batters) { b in
                    TopPlayerRow(
                        name: b.player, team: team, league: league,
                        stats: [
                            ("AVG", String(format: "%.3f", b.AVG)),
                            ("HR",  "\(b.HR)"),
                            ("RBI", "\(b.RBI)"),
                            ("GP",  "\(b.games)"),
                        ],
                        onTap: { onSelect(b.player) }
                    )
                }
            }
            if let pitchers = tp.pitchers, role == "pitcher" {
                ForEach(pitchers) { p in
                    TopPlayerRow(
                        name: p.player, team: team, league: league,
                        stats: [
                            ("ERA",  String(format: "%.2f", p.ERA)),
                            ("WHIP", String(format: "%.2f", p.WHIP)),
                            ("SO",   "\(p.SO)"),
                            ("IP",   String(format: "%.1f", p.IP)),
                        ],
                        onTap: { onSelect(p.player) }
                    )
                }
            }
        }
    }
}

private struct TopPlayerRow: View {
    let name: String
    let team: String
    let league: String
    let stats: [(String, String)]
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                if !team.isEmpty {
                    TeamBadge(team: team, league: league, size: 34)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(name).font(.system(size: 14, weight: .semibold)).foregroundColor(.csText).lineLimit(1)
                    if !team.isEmpty {
                        Text(team).font(.system(size: 11)).foregroundColor(.csSub).lineLimit(1)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 6) {
                    ForEach(stats, id: \.0) { label, value in
                        VStack(spacing: 2) {
                            Text(value).font(.csMono(13, weight: .bold)).foregroundColor(.csText)
                            Text(label).font(.system(size: 9, weight: .bold)).kerning(0.5).foregroundColor(.csSub)
                        }
                        .frame(minWidth: 34)
                    }
                }
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .bold)).foregroundColor(.csFaint)
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .background(Color.csCard)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Player Detail

struct PlayerDetailView: View {
    let player: String
    let sport: Sport
    let role: String
    let teams: [String]
    var teamContext: String = ""
    let onBack: () -> Void

    @State private var stats: [(String, String)] = []
    @State private var log: [[String: String]] = []
    @State private var vsTeam = ""
    @State private var vsStats: [(String, String)] = []
    @State private var projection: PlayerProjection? = nil
    @State private var loadingStats = false
    @State private var loadingVs = false
    @State private var loadingProj = false

    private var isMLB: Bool { sport == .MLB }
    private var leagueAccent: Color { isMLB ? .csMLB : .csNBA }

    private var logColumns: [String] {
        if isMLB {
            return role == "pitcher"
                ? ["date", "opponent", "innings_pitched", "earned_runs", "strikeouts_pitched", "walks_allowed"]
                : ["date", "opponent", "at_bats", "hits", "home_runs", "rbi"]
        }
        return ["date", "opponent", "points", "assists", "rebounds"]
    }

    private let colLabels: [String: String] = [
        "date": "Date", "opponent": "Opp", "innings_pitched": "IP",
        "earned_runs": "ER", "strikeouts_pitched": "K", "walks_allowed": "BB",
        "at_bats": "AB", "hits": "H", "home_runs": "HR", "rbi": "RBI",
        "points": "PTS", "assists": "AST", "rebounds": "REB",
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                backButton
                hero

                if loadingStats {
                    HStack { Spacer(); ProgressView().tint(.csNBA); Spacer() }.padding(.top, 20)
                } else {
                    if !stats.isEmpty { seasonStatsCard }
                    vsOpponentCard
                    if isMLB && (projection != nil || loadingProj) { projectedCard }
                    gameLogCard
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 4)
            .padding(.bottom, 40)
        }
        .background(Color.csBg.ignoresSafeArea())
        .task { await loadStats() }
        .onChange(of: vsTeam) { _, _ in
            guard !vsTeam.isEmpty else { vsStats = []; projection = nil; return }
            Task { await loadVs() }
            if isMLB { Task { await loadProjected() } }
        }
    }

    private var backButton: some View {
        Button(action: onBack) {
            HStack(spacing: 4) {
                Image(systemName: "chevron.left").font(.system(size: 13, weight: .bold))
                Text("Players").font(.system(size: 14, weight: .semibold))
            }
            .foregroundColor(.csNBA)
        }
    }

    private var hero: some View {
        let teamColor = teamContext.isEmpty ? leagueAccent : TeamStyle.lookup(teamContext, league: sport.rawValue).color
        return ZStack(alignment: .topLeading) {
            LinearGradient(
                colors: [teamColor, teamColor.opacity(0.75)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    if !teamContext.isEmpty {
                        TeamBadge(team: teamContext, league: sport.rawValue, size: 48)
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text(teamContext.isEmpty ? sport.rawValue.uppercased() : "\(teamContext) · \(sport.rawValue)")
                            .font(.csSection)
                            .kerning(1.0)
                            .foregroundColor(.white.opacity(0.85))
                        Text(player)
                            .font(.csEditorial(30))
                            .foregroundColor(.white)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                    Spacer(minLength: 0)
                }

                if !stats.isEmpty {
                    HStack(spacing: 8) {
                        ForEach(stats.prefix(4), id: \.0) { label, value in
                            VStack(spacing: 2) {
                                Text(value).font(.csMono(15, weight: .bold)).foregroundColor(.white)
                                Text(label.uppercased()).font(.system(size: 9, weight: .bold)).kerning(0.5).foregroundColor(.white.opacity(0.8))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(Color.white.opacity(0.18))
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        }
                    }
                }
            }
            .padding(18)
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var seasonStatsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Season Stats")
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(stats, id: \.0) { key, value in
                    StatBox(value: value, label: key, accent: .csText)
                }
            }
        }
    }

    private var vsOpponentCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "vs Opponent") {
                Menu {
                    Button("Select team") { vsTeam = "" }
                    ForEach(teams, id: \.self) { t in
                        Button(t) { vsTeam = t }
                    }
                } label: {
                    HStack(spacing: 6) {
                        Text(vsTeam.isEmpty ? "Select team" : vsTeam)
                            .font(.system(size: 12, weight: .semibold)).foregroundColor(.csText).lineLimit(1)
                        Image(systemName: "chevron.down").font(.system(size: 10, weight: .bold)).foregroundColor(.csSub)
                    }
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .background(Color.csChip)
                    .clipShape(Capsule())
                }
            }

            if loadingVs {
                ProgressView().tint(.csNBA).scaleEffect(0.8)
            } else if !vsStats.isEmpty {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                    ForEach(vsStats, id: \.0) { key, value in
                        StatBox(value: value, label: key, accent: leagueAccent)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var projectedCard: some View {
        if loadingProj && projection == nil {
            VStack(alignment: .leading, spacing: 10) {
                SectionHeader(title: "Projected")
                ProgressView().tint(.csNBA).scaleEffect(0.8)
            }
        } else if let p = projection {
            VStack(alignment: .leading, spacing: 10) {
                SectionHeader(title: "Projected vs \(p.opponent)")
                Text("Confidence \(p.confidence.uppercased())  ·  H2H \(p.h2h_games)  ·  \(p.season_games_used) games"
                     + (p.streak_context == "hot" ? "  ·  🔥 hot"
                        : p.streak_context == "cold" ? "  ·  ❄️ cold" : ""))
                    .font(.system(size: 11)).foregroundColor(.csSub)
                if let inj = p.injury_status, !inj.isEmpty,
                   inj != "active", inj != "probable" {
                    Text("⚠️ \(inj.uppercased())" + (p.injury_detail.map { " · \($0)" } ?? ""))
                        .font(.system(size: 11, weight: .semibold)).foregroundColor(.orange)
                }
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                    ForEach(projTiles(p), id: \.0) { label, value in
                        StatBox(value: value, label: label, accent: leagueAccent)
                    }
                }
            }
        }
    }

    private func projTiles(_ p: PlayerProjection) -> [(String, String)] {
        func f(_ d: [String: Double], _ k: String, _ dec: Int) -> String {
            d[k].map { String(format: "%.\(dec)f", $0) } ?? "—"
        }
        if role == "pitcher" {
            return [
                ("ERA",  f(p.derived,   "ERA", 2)),
                ("WHIP", f(p.derived,   "WHIP", 2)),
                ("K",    f(p.projected, "strikeouts_pitched", 1)),
                ("IP",   f(p.projected, "innings_pitched", 1)),
                ("ER",   f(p.projected, "earned_runs", 1)),
                ("H",    f(p.projected, "hits_allowed", 1)),
                ("BB",   f(p.projected, "walks_allowed", 1)),
            ]
        }
        let avg = p.derived["AVG"].map {
            String(format: "%.3f", $0).replacingOccurrences(of: "0.", with: ".")
        } ?? "—"
        return [
            ("AVG", avg),
            ("H",   f(p.projected, "hits", 1)),
            ("HR",  f(p.projected, "home_runs", 2)),
            ("RBI", f(p.projected, "rbi", 1)),
            ("R",   f(p.projected, "runs", 1)),
            ("BB",  f(p.projected, "walks", 1)),
            ("SO",  f(p.projected, "strikeouts", 1)),
        ]
    }

    private var gameLogCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Game Log")
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    ForEach(logColumns, id: \.self) { col in
                        Text(colLabels[col] ?? col)
                            .font(.csSection).kerning(0.8)
                            .foregroundColor(.csSub)
                            .frame(maxWidth: .infinity, alignment: .center)
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
                Divider().background(Color.csBorder)
                ForEach(Array(log.enumerated()), id: \.offset) { i, row in
                    HStack(spacing: 0) {
                        ForEach(logColumns, id: \.self) { col in
                            let val = col == "opponent"
                                ? (row[col] ?? "").split(separator: " ").last.map(String.init) ?? row[col] ?? "–"
                                : row[col] ?? "–"
                            Text(val)
                                .font(.csMono(12, weight: col == "date" || col == "opponent" ? .regular : .semibold))
                                .foregroundColor(.csText)
                                .frame(maxWidth: .infinity, alignment: .center)
                                .lineLimit(1)
                        }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    if i < log.count - 1 { Divider().background(Color.csBorder) }
                }
            }
            .background(Color.csCard)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }

    private func loadStats() async {
        loadingStats = true
        async let s = API.playerStats(league: sport, name: player, role: role)
        async let l = API.playerLog(league: sport, name: player, role: role)
        do { (stats, log) = try await (s, l) } catch {}
        loadingStats = false
    }

    private func loadVs() async {
        loadingVs = true
        do { vsStats = try await API.playerVsTeam(league: sport, name: player, opponent: vsTeam, role: role) }
        catch { vsStats = [] }
        loadingVs = false
    }

    private func loadProjected() async {
        loadingProj = true
        do { projection = try await API.playerProjected(league: sport, name: player, opponent: vsTeam, role: role) }
        catch { projection = nil }
        loadingProj = false
    }
}
