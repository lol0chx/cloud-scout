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
                Color.csBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    header
                        .padding(.horizontal, 18)
                        .padding(.top, 4)
                        .padding(.bottom, 14)

                    controls
                        .padding(.horizontal, 16)
                        .padding(.bottom, 10)

                    if !error.isEmpty {
                        Text(error).foregroundColor(.csLive).padding()
                        Spacer()
                    } else if loading && games.isEmpty {
                        Spacer(); ProgressView().tint(.csNBA); Spacer()
                    } else if games.isEmpty {
                        Spacer()
                        VStack(spacing: 8) {
                            Image(systemName: "sportscourt").font(.system(size: 40)).foregroundColor(.csBorder)
                            Text("No games yet").font(.system(size: 16, weight: .semibold)).foregroundColor(.csSub)
                            Text("Go to Update tab to scrape data").font(.system(size: 13)).foregroundColor(.csBorder)
                        }
                        Spacer()
                    } else {
                        ScrollView(.vertical, showsIndicators: false) {
                            LazyVStack(alignment: .leading, spacing: 16) {
                                ForEach(groupedGames, id: \.label) { group in
                                    VStack(alignment: .leading, spacing: 8) {
                                        SectionHeader(title: group.label)
                                            .padding(.horizontal, 2)
                                        VStack(spacing: 8) {
                                            ForEach(group.games) { game in
                                                NavigationLink {
                                                    GameDetailView(game: game, selectedTeam: team)
                                                } label: {
                                                    CompactGameRow(game: game, highlightTeam: team)
                                                }
                                                .buttonStyle(.plain)
                                            }
                                        }
                                    }
                                }
                                Spacer(minLength: 20)
                            }
                            .padding(.horizontal, 16)
                            .padding(.top, 4)
                        }
                        .refreshable { await load() }
                    }
                }
            }
            .toolbarBackground(Color.csBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: team) { _, _ in Task { await load() } }
    }

    private var header: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 2) {
                Text("SCOREBOARD")
                    .font(.csSection)
                    .kerning(1.0)
                    .foregroundColor(.csSub)
                Text("Games")
                    .font(.csEditorial(40))
                    .foregroundColor(.csText)
            }
            Spacer()
            Button { Task { await load() } } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.csNBA)
                    .frame(width: 36, height: 36)
                    .background(Color.csCard)
                    .clipShape(Circle())
                    .overlay(Circle().strokeBorder(Color.csBorder, lineWidth: 1))
            }
        }
    }

    private var controls: some View {
        VStack(spacing: 10) {
            SportToggle(sport: $state.sport)
            if !teams.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "line.3.horizontal.decrease.circle")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.csSub)
                    Picker("Team", selection: $team) {
                        Text("All teams").tag("")
                        ForEach(teams, id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.menu).tint(.csText)
                    Spacer()
                }
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Color.csCard)
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(Color.csBorder, lineWidth: 1))
            }
        }
    }

    private struct GameGroup {
        let label: String
        let games: [Game]
    }

    private var groupedGames: [GameGroup] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        let outFmt = DateFormatter()
        outFmt.dateFormat = "EEE · MMM d"

        var buckets: [(String, Int, [Game])] = []
        for game in games {
            guard let d = inFmt.date(from: game.date) else { continue }
            let day = cal.startOfDay(for: d)
            let days = cal.dateComponents([.day], from: day, to: today).day ?? 0
            let label: String
            switch days {
            case 0: label = "Today · \(outFmt.string(from: d))"
            case 1: label = "Yesterday · \(outFmt.string(from: d))"
            default: label = outFmt.string(from: d)
            }
            if let i = buckets.firstIndex(where: { $0.1 == days }) {
                buckets[i].2.append(game)
            } else {
                buckets.append((label, days, [game]))
            }
        }
        buckets.sort { $0.1 < $1.1 }
        return buckets.map { GameGroup(label: $0.0, games: $0.2) }
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

// MARK: - CompactGameRow

struct CompactGameRow: View {
    let game: Game
    var highlightTeam: String = ""

    private var homeWon: Bool { game.home_score > game.away_score }
    private var hasScore: Bool { game.home_score != 0 || game.away_score != 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                StatusPill(kind: .final, text: "Final")
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.csFaint)
            }

            VStack(spacing: 6) {
                teamRow(team: game.away_team, score: game.away_score, won: !homeWon)
                teamRow(team: game.home_team, score: game.home_score, won: homeWon)
            }
        }
        .csCard(radius: 14, padding: EdgeInsets(top: 12, leading: 14, bottom: 12, trailing: 14))
    }

    @ViewBuilder
    private func teamRow(team: String, score: Int, won: Bool) -> some View {
        let dimmed = hasScore && !won
        HStack(spacing: 10) {
            TeamBadge(team: team, league: game.league, size: 26)
                .opacity(dimmed ? 0.55 : 1.0)
            Text(team)
                .font(.system(size: 14, weight: dimmed ? .regular : .semibold))
                .foregroundColor(dimmed ? .csSub : .csText)
                .lineLimit(1)
            Spacer(minLength: 0)
            if hasScore {
                Text("\(score)")
                    .font(.csMono(17, weight: won ? .bold : .regular))
                    .foregroundColor(dimmed ? .csSub : .csText)
                    .monospacedDigit()
            }
        }
    }
}
