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
                Color.appBg.ignoresSafeArea()
                if let player = selectedPlayer {
                    PlayerDetailView(
                        player: player,
                        sport: state.sport,
                        role: role.rawValue,
                        teams: teams,
                        onBack: { selectedPlayer = nil }
                    )
                } else {
                    VStack(spacing: 0) {
                        // Header
                        VStack(alignment: .leading, spacing: 0) {
                            Text("Players")
                                .font(.system(size: 20, weight: .bold))
                                .foregroundColor(.white)
                                .padding(.bottom, 12)
                            SportPicker(sport: $state.sport)

                            if isMLB {
                                HStack(spacing: 8) {
                                    ForEach(PlayerRole.allCases, id: \.self) { r in
                                        Button { role = r } label: {
                                            Text(r.label)
                                                .font(.system(size: 13, weight: .semibold))
                                                .foregroundColor(role == r ? .appPrimary : .appSub)
                                                .frame(maxWidth: .infinity).padding(.vertical, 8)
                                                .background(
                                                    RoundedRectangle(cornerRadius: 8)
                                                        .strokeBorder(role == r ? Color.appPrimary : Color.appBorder)
                                                        .background((role == r ? Color.appPrimary.opacity(0.1) : Color.clear).clipShape(RoundedRectangle(cornerRadius: 8)))
                                                )
                                        }
                                    }
                                }
                                .padding(.bottom, 10)
                            }

                            TextField("Search player...", text: $search)
                                .textFieldStyle(.plain).foregroundColor(.white)
                                .padding(.horizontal, 12).padding(.vertical, 9)
                                .background(Color.appCard)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.appBorder))
                                .padding(.bottom, 8)
                        }
                        .padding(.horizontal, 16).padding(.top, 16)

                        if loadingPlayers {
                            ProgressView().tint(.appPrimary).padding(.bottom, 8)
                        }

                        // Top Performers
                        if search.isEmpty {
                            ScrollView {
                                VStack(alignment: .leading, spacing: 0) {
                                    // Team selector for top performers
                                    HStack {
                                        Text("Top Performers —").font(.system(size: 13, weight: .semibold)).foregroundColor(.appSub)
                                        Picker("", selection: $topTeam) {
                                            ForEach(teams, id: \.self) { Text($0).tag($0) }
                                        }
                                        .pickerStyle(.menu).tint(.appPrimary)
                                    }
                                    .padding(.horizontal, 16).padding(.bottom, 8)

                                    if loadingTop {
                                        HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 20)
                                    } else if let tp = topPerformers {
                                        TopPerformersSection(tp: tp, isMLB: isMLB, role: role.rawValue) { name in
                                            selectedPlayer = name
                                        }
                                        .padding(.horizontal, 16)
                                    }

                                    // Player list
                                    Text("ALL PLAYERS")
                                        .font(.system(size: 12, weight: .semibold)).foregroundColor(.appSub).kerning(0.8)
                                        .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 6)

                                    ForEach(players.prefix(50), id: \.self) { name in
                                        Button { selectedPlayer = name } label: {
                                            HStack {
                                                Text(name).foregroundColor(.white).font(.system(size: 15))
                                                Spacer()
                                                Text("›").foregroundColor(.appSub)
                                            }
                                            .padding(.horizontal, 16).padding(.vertical, 13)
                                        }
                                        Divider().background(Color.appBorder).padding(.horizontal, 16)
                                    }
                                }
                                .padding(.bottom, 40)
                            }
                        } else {
                            List(players.prefix(50), id: \.self) { name in
                                Button { selectedPlayer = name } label: {
                                    HStack {
                                        Text(name).foregroundColor(.white).font(.system(size: 15))
                                        Spacer()
                                        Text("›").foregroundColor(.appSub)
                                    }
                                }
                                .listRowBackground(Color.appBg)
                                .listRowSeparatorTint(Color.appBorder)
                            }
                            .listStyle(.plain)
                        }
                    }
                }
            }
        }
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

// MARK: - Top Performers

private struct TopPerformersSection: View {
    let tp: TopPerformersResponse
    let isMLB: Bool
    let role: String
    let onSelect: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let players = tp.players {
                ForEach(players) { p in
                    TopPlayerRow(name: p.player, stats: [
                        ("PTS", String(format: "%.1f", p.avg_points)),
                        ("AST", String(format: "%.1f", p.avg_assists)),
                        ("REB", String(format: "%.1f", p.avg_rebounds)),
                        ("GP",  "\(p.games)"),
                    ], onTap: { onSelect(p.player) })
                }
            }
            if let batters = tp.batters, role == "batter" {
                ForEach(batters) { b in
                    TopPlayerRow(name: b.player, stats: [
                        ("AVG", String(format: "%.3f", b.AVG)),
                        ("HR",  "\(b.HR)"),
                        ("RBI", "\(b.RBI)"),
                        ("GP",  "\(b.games)"),
                    ], onTap: { onSelect(b.player) })
                }
            }
            if let pitchers = tp.pitchers, role == "pitcher" {
                ForEach(pitchers) { p in
                    TopPlayerRow(name: p.player, stats: [
                        ("ERA",  String(format: "%.2f", p.ERA)),
                        ("WHIP", String(format: "%.2f", p.WHIP)),
                        ("SO",   "\(p.SO)"),
                        ("IP",   String(format: "%.1f", p.IP)),
                    ], onTap: { onSelect(p.player) })
                }
            }
        }
    }
}

private struct TopPlayerRow: View {
    let name: String
    let stats: [(String, String)]
    let onTap: () -> Void
    var body: some View {
        Button(action: onTap) {
            HStack {
                Text(name).font(.system(size: 14, weight: .semibold)).foregroundColor(.white).frame(maxWidth: .infinity, alignment: .leading).lineLimit(1)
                ForEach(stats, id: \.0) { label, value in
                    VStack(spacing: 2) {
                        Text(value).font(.system(size: 13, weight: .bold)).foregroundColor(.white)
                        Text(label).font(.system(size: 10)).foregroundColor(.appSub)
                    }
                    .frame(minWidth: 40)
                }
                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundColor(.appSub)
            }
            .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}

// MARK: - Player Detail

struct PlayerDetailView: View {
    let player: String
    let sport: Sport
    let role: String
    let teams: [String]
    let onBack: () -> Void

    @State private var stats: [(String, String)] = []
    @State private var log: [[String: String]] = []
    @State private var vsTeam = ""
    @State private var vsStats: [(String, String)] = []
    @State private var loadingStats = false
    @State private var loadingVs = false

    private var isMLB: Bool { sport == .MLB }

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
            VStack(alignment: .leading, spacing: 0) {
                Button(action: onBack) {
                    Label("Back to list", systemImage: "chevron.left")
                        .font(.system(size: 14)).foregroundColor(.appPrimary)
                }
                .padding(.horizontal, 16).padding(.top, 16).padding(.bottom, 8)

                Text(player)
                    .font(.system(size: 20, weight: .bold)).foregroundColor(.white)
                    .padding(.horizontal, 16).padding(.bottom, 12)

                if loadingStats {
                    HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 20)
                } else {
                    // Season stats grid
                    if !stats.isEmpty {
                        sectionHeader("Season Stats")
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                            ForEach(stats, id: \.0) { key, value in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(key).font(.system(size: 11)).foregroundColor(.appSub)
                                    Text(value).font(.system(size: 15, weight: .semibold)).foregroundColor(.white)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                                .background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                        .padding(.horizontal, 16)
                    }

                    // Player vs Team
                    sectionHeader("vs Opponent")
                    HStack {
                        Picker("Opponent", selection: $vsTeam) {
                            Text("Select team").tag("")
                            ForEach(teams, id: \.self) { Text($0).tag($0) }
                        }
                        .pickerStyle(.menu).tint(.appSub)
                        .padding(8).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 8))
                        if loadingVs { ProgressView().tint(.appPrimary).scaleEffect(0.8) }
                    }
                    .padding(.horizontal, 16).padding(.bottom, 8)

                    if !vsStats.isEmpty {
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                            ForEach(vsStats, id: \.0) { key, value in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(key).font(.system(size: 11)).foregroundColor(.appSub)
                                    Text(value).font(.system(size: 15, weight: .semibold)).foregroundColor(.appMLB)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                                .background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                        .padding(.horizontal, 16)
                    }

                    // Game Log
                    sectionHeader("Game Log")
                    HStack {
                        ForEach(logColumns, id: \.self) { col in
                            Text(colLabels[col] ?? col).font(.system(size: 11)).foregroundColor(.appSub).frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.horizontal, 16).padding(.vertical, 6)
                    Divider().background(Color.appBorder).padding(.horizontal, 16)

                    ForEach(Array(log.enumerated()), id: \.offset) { _, row in
                        HStack {
                            ForEach(logColumns, id: \.self) { col in
                                let val = col == "opponent"
                                    ? (row[col] ?? "").split(separator: " ").last.map(String.init) ?? row[col] ?? "–"
                                    : row[col] ?? "–"
                                Text(val).font(.system(size: 13)).foregroundColor(.white).frame(maxWidth: .infinity).lineLimit(1)
                            }
                        }
                        .padding(.horizontal, 16).padding(.vertical, 10)
                        Divider().background(Color.appBorder).padding(.horizontal, 16)
                    }
                }
            }
            .padding(.bottom, 40)
        }
        .background(Color.appBg.ignoresSafeArea())
        .task { await loadStats() }
        .onChange(of: vsTeam) { _, _ in
            guard !vsTeam.isEmpty else { vsStats = []; return }
            Task { await loadVs() }
        }
    }

    @ViewBuilder
    private func sectionHeader(_ t: String) -> some View {
        Text(t.uppercased())
            .font(.system(size: 12, weight: .semibold)).foregroundColor(.appSub).kerning(0.8)
            .padding(.horizontal, 16).padding(.top, 16).padding(.bottom, 8)
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
}
