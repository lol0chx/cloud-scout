import SwiftUI

struct PlayersView: View {
    @EnvironmentObject var state: AppState
    @State private var role: PlayerRole = .batter
    @State private var search = ""
    @State private var players: [String] = []
    @State private var selectedPlayer: String?
    @State private var stats: [(String, String)] = []
    @State private var gameCount = 0
    @State private var log: [[String: String]] = []
    @State private var loading = false
    @State private var loadingPlayers = false
    @State private var searchTask: Task<Void, Never>?

    enum PlayerRole: String, CaseIterable {
        case batter, pitcher
        var label: String { self == .batter ? "Batters" : "Pitchers" }
    }

    private var isMLB: Bool { state.sport == .MLB }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.appBg.ignoresSafeArea()
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
                                    Button { role = r; selectedPlayer = nil } label: {
                                        Text(r.label)
                                            .font(.system(size: 13, weight: .semibold))
                                            .foregroundColor(role == r ? .appPrimary : .appSub)
                                            .frame(maxWidth: .infinity)
                                            .padding(.vertical, 8)
                                            .background(
                                                RoundedRectangle(cornerRadius: 8)
                                                    .strokeBorder(role == r ? Color.appPrimary : Color.appBorder)
                                                    .background(role == r ? Color.appPrimary.opacity(0.1) : Color.clear)
                                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                                            )
                                    }
                                }
                            }
                            .padding(.bottom, 10)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)

                    if let player = selectedPlayer {
                        PlayerDetailView(
                            player: player,
                            stats: stats,
                            gameCount: gameCount,
                            log: log,
                            loading: loading,
                            isMLB: isMLB,
                            role: role.rawValue,
                            onBack: { selectedPlayer = nil }
                        )
                    } else {
                        // Search
                        TextField("Search player...", text: $search)
                            .textFieldStyle(.plain)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 9)
                            .background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.appBorder))
                            .padding(.horizontal, 16)
                            .padding(.bottom, 8)

                        if loadingPlayers {
                            ProgressView().tint(.appPrimary).padding(.bottom, 8)
                        }

                        List(players.prefix(50), id: \.self) { name in
                            Button {
                                selectedPlayer = name
                                Task { await loadPlayerStats(name) }
                            } label: {
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
        .task { await loadPlayers() }
        .onChange(of: state.sport) { _, _ in selectedPlayer = nil; search = ""; Task { await loadPlayers() } }
        .onChange(of: role) { _, _ in Task { await loadPlayers() } }
        .onChange(of: search) { _, _ in
            searchTask?.cancel()
            searchTask = Task {
                try? await Task.sleep(nanoseconds: 300_000_000)
                if !Task.isCancelled { await loadPlayers() }
            }
        }
    }

    private func loadPlayers() async {
        loadingPlayers = true
        do { players = try await API.players(league: state.sport, name: search, role: isMLB ? role.rawValue : "") }
        catch { players = [] }
        loadingPlayers = false
    }

    private func loadPlayerStats(_ name: String) async {
        loading = true; stats = []; log = []
        async let s = API.playerStats(league: state.sport, name: name, role: role.rawValue)
        async let l = API.playerLog(league: state.sport, name: name, role: role.rawValue)
        do {
            let (fetchedStats, fetchedLog) = try await (s, l)
            stats = fetchedStats
            log = fetchedLog
        } catch {}
        loading = false
    }
}

private struct PlayerDetailView: View {
    let player: String
    let stats: [(String, String)]
    let gameCount: Int
    let log: [[String: String]]
    let loading: Bool
    let isMLB: Bool
    let role: String
    let onBack: () -> Void

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
                        .font(.system(size: 14))
                        .foregroundColor(.appPrimary)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 8)

                Text(player)
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 4)

                if loading {
                    HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 20)
                } else {
                    // Stats grid
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                        ForEach(stats, id: \.0) { key, value in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(key).font(.system(size: 12)).foregroundColor(.appSub)
                                Text(value).font(.system(size: 16, weight: .semibold)).foregroundColor(.white)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10)
                            .background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)

                    // Log header
                    Text("GAME LOG")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.appSub)
                        .kerning(0.8)
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 6)

                    HStack {
                        ForEach(logColumns, id: \.self) { col in
                            Text(colLabels[col] ?? col)
                                .font(.system(size: 11))
                                .foregroundColor(.appSub)
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 4)
                    Divider().background(Color.appBorder).padding(.horizontal, 16)

                    ForEach(Array(log.enumerated()), id: \.offset) { _, row in
                        HStack {
                            ForEach(logColumns, id: \.self) { col in
                                let val = col == "opponent"
                                    ? (row[col] ?? "").split(separator: " ").last.map(String.init) ?? row[col] ?? "–"
                                    : row[col] ?? "–"
                                Text(val)
                                    .font(.system(size: 13))
                                    .foregroundColor(.white)
                                    .frame(maxWidth: .infinity)
                                    .lineLimit(1)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        Divider().background(Color.appBorder).padding(.horizontal, 16)
                    }
                }
            }
            .padding(.bottom, 40)
        }
    }
}
