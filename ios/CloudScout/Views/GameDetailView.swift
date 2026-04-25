import SwiftUI

struct GameDetailView: View {
    let game: Game
    var selectedTeam: String = ""

    @State private var awayLeaders: [LeaderEntry] = []
    @State private var homeLeaders: [LeaderEntry] = []
    @State private var teams: [String] = []

    private var homeWon: Bool { game.home_score > game.away_score }
    private var isTeamHome: Bool { game.home_team == selectedTeam }
    private var teamWon: Bool { isTeamHome ? homeWon : !homeWon }
    private var hasTeam: Bool {
        !selectedTeam.isEmpty && (game.home_team == selectedTeam || game.away_team == selectedTeam)
    }
    private var hasScore: Bool { game.home_score != 0 || game.away_score != 0 }
    private var leagueColor: Color { game.league == "MLB" ? .csMLB : .csNBA }
    private var sport: Sport { game.league == "MLB" ? .MLB : .NBA }

    private var topLeaders: [LeaderEntry] {
        let combined = (awayLeaders + homeLeaders).sorted { $0.sortKey > $1.sortKey }
        return Array(combined.prefix(4))
    }

    var body: some View {
        ZStack {
            Color.csBg.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 10) {
                    heroCard
                    if !topLeaders.isEmpty { leadersSection }
                    detailsCard
                    if hasTeam { resultCard }
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 40)
            }
        }
        .navigationTitle(game.league)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.csBg, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .preferredColorScheme(.light)
        .task { await loadLeaders() }
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                StatusPill(kind: hasScore ? .final : .scheduled, text: hasScore ? "Final" : "Scheduled")
                Spacer()
                Text(formattedDate)
                    .font(.system(size: 12, weight: .semibold))
                    .kerning(0.8)
                    .foregroundColor(.csSub)
            }

            HStack(alignment: .center, spacing: 12) {
                teamColumn(team: game.away_team, score: game.away_score, won: !homeWon, isAway: true)
                Text("–")
                    .font(.csMono(32, weight: .regular))
                    .foregroundColor(.csFaint)
                teamColumn(team: game.home_team, score: game.home_score, won: homeWon, isAway: false)
            }
        }
        .csCard(radius: 18, padding: EdgeInsets(top: 18, leading: 18, bottom: 20, trailing: 18))
    }

    @ViewBuilder
    private func teamColumn(team: String, score: Int, won: Bool, isAway: Bool) -> some View {
        VStack(spacing: 8) {
            TeamBadge(team: team, league: game.league, size: 48)
            Text(TeamStyle.lookup(team, league: game.league).abbr)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.csText)
            Text("\(score)")
                .font(.csMono(44, weight: .bold))
                .foregroundColor(hasScore && won ? leagueColor : hasScore ? .csSub : .csFaint)
                .monospacedDigit()
            Text(isAway ? "AWAY" : "HOME")
                .font(.csSection)
                .kerning(1.0)
                .foregroundColor(.csFaint)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Leaders

    private var leadersSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionHeader(title: "Leaders")
                .padding(.horizontal, 4)
            VStack(spacing: 8) {
                ForEach(topLeaders) { leader in
                    NavigationLink {
                        PlayerDetailView(
                            player: leader.name,
                            sport: sport,
                            role: leader.role,
                            teams: teams,
                            teamContext: leader.team,
                            onBack: {}
                        )
                    } label: {
                        LeaderRow(leader: leader, league: game.league)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.top, 4)
    }

    private var detailsCard: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Game")
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 6)
            VStack(spacing: 0) {
                DetailRow(label: "League", value: game.league)
                Divider().background(Color.csBorder)
                DetailRow(label: "Season", value: game.season)
                if hasScore {
                    Divider().background(Color.csBorder)
                    DetailRow(
                        label: "Margin",
                        value: "\(abs(game.home_score - game.away_score)) \(game.league == "MLB" ? "runs" : "pts")"
                    )
                    Divider().background(Color.csBorder)
                    DetailRow(
                        label: "Total",
                        value: "\(game.home_score + game.away_score) \(game.league == "MLB" ? "runs" : "pts")"
                    )
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var resultCard: some View {
        HStack {
            Text(teamWon ? "Win" : "Loss")
                .font(.system(size: 14, weight: .heavy))
                .foregroundColor(teamWon ? .csWin : .csLoss)
            Text("·").foregroundColor(.csFaint)
            Text("\(selectedTeam) · \(isTeamHome ? "Home" : "Away")")
                .font(.system(size: 13))
                .foregroundColor(.csSub)
            Spacer()
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background((teamWon ? Color.csWin : Color.csLoss).opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var formattedDate: String {
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        guard let d = inFmt.date(from: game.date) else { return game.date }
        let out = DateFormatter()
        out.dateFormat = "EEE · MMM d"
        return out.string(from: d).uppercased()
    }

    private func loadLeaders() async {
        async let awayPerf = API.topPerformers(league: sport, team: game.away_team, n: 8)
        async let homePerf = API.topPerformers(league: sport, team: game.home_team, n: 8)
        async let teamList = API.teams(league: sport)
        let away = (try? await awayPerf)
        let home = (try? await homePerf)
        self.teams = (try? await teamList) ?? []
        self.awayLeaders = leaders(from: away, team: game.away_team).prefix(3).map { $0 }
        self.homeLeaders = leaders(from: home, team: game.home_team).prefix(3).map { $0 }
    }

    private func leaders(from perf: TopPerformersResponse?, team: String) -> [LeaderEntry] {
        guard let perf else { return [] }
        if let players = perf.players {
            return players.sorted { $0.avg_points > $1.avg_points }.map {
                LeaderEntry(
                    name: $0.player,
                    team: team,
                    role: "",
                    statLine: "\(fmt($0.avg_points)) PTS · \(fmt($0.avg_rebounds)) REB · \(fmt($0.avg_assists)) AST",
                    sortKey: $0.avg_points
                )
            }
        }
        var combined: [LeaderEntry] = []
        if let batters = perf.batters {
            combined.append(contentsOf: batters.sorted { $0.AVG > $1.AVG }.map {
                LeaderEntry(
                    name: $0.player,
                    team: team,
                    role: "batter",
                    statLine: "\(fmt3($0.AVG)) AVG · \($0.HR) HR · \($0.RBI) RBI",
                    sortKey: $0.AVG * 100
                )
            })
        }
        if let pitchers = perf.pitchers {
            combined.append(contentsOf: pitchers.sorted { $0.ERA < $1.ERA }.map {
                LeaderEntry(
                    name: $0.player,
                    team: team,
                    role: "pitcher",
                    statLine: "\(fmt2($0.ERA)) ERA · \(fmt2($0.WHIP)) WHIP · \($0.SO) K",
                    sortKey: max(0, 10 - $0.ERA) * 10
                )
            })
        }
        return combined
    }

    private func fmt(_ v: Double) -> String { String(format: "%.1f", v) }
    private func fmt2(_ v: Double) -> String { String(format: "%.2f", v) }
    private func fmt3(_ v: Double) -> String { String(format: "%.3f", v) }
}

struct LeaderEntry: Identifiable {
    var id: String { "\(name)_\(team)_\(role)" }
    let name: String
    let team: String
    let role: String
    let statLine: String
    let sortKey: Double
}

private struct LeaderRow: View {
    let leader: LeaderEntry
    let league: String

    var body: some View {
        HStack(spacing: 12) {
            TeamBadge(team: leader.team, league: league, size: 36)
            VStack(alignment: .leading, spacing: 3) {
                Text(leader.name)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.csText)
                    .lineLimit(1)
                Text(leader.statLine)
                    .font(.csMono(12, weight: .semibold))
                    .foregroundColor(.csSub)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(.csFaint)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

private struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label).font(.system(size: 14)).foregroundColor(.csSub)
            Spacer()
            Text(value).font(.system(size: 14, weight: .semibold)).foregroundColor(.csText)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
    }
}
