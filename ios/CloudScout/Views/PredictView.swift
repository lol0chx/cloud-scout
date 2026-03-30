import SwiftUI

struct PredictView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var teamA = ""
    @State private var teamB = ""
    @State private var prediction: Prediction?
    @State private var h2h: H2HResponse?
    @State private var homeAwayA: HomeAwayStats?
    @State private var homeAwayB: HomeAwayStats?
    @State private var formA: TeamForm?
    @State private var formB: TeamForm?
    @State private var advancedH2H: H2HAdvancedResponse?
    @State private var projTotal: ProjectedTotalResponse?
    @State private var injuriesA: [Injury] = []
    @State private var injuriesB: [Injury] = []
    @State private var todayMatchup: TodayGame?
    @State private var starters: StartersResponse?
    @State private var loading = false
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Predictions")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.bottom, 12)
                    SportPicker(sport: $state.sport)

                    // Team pickers
                    HStack(alignment: .bottom, spacing: 8) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Team A").font(.system(size: 12)).foregroundColor(.appSub)
                            Picker("Team A", selection: $teamA) {
                                ForEach(teams, id: \.self) { Text($0).tag($0) }
                            }
                            .pickerStyle(.menu).tint(.appSub)
                            .frame(maxWidth: .infinity)
                            .padding(8).background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        Text("vs").foregroundColor(.appSub).padding(.bottom, 12)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Team B").font(.system(size: 12)).foregroundColor(.appSub)
                            Picker("Team B", selection: $teamB) {
                                ForEach(teams, id: \.self) { Text($0).tag($0) }
                            }
                            .pickerStyle(.menu).tint(.appSub)
                            .frame(maxWidth: .infinity)
                            .padding(8).background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                    .padding(.bottom, 12)

                    if teamA == teamB && !teamA.isEmpty {
                        Text("Select two different teams.")
                            .font(.system(size: 13)).foregroundColor(.appMLB).padding(.bottom, 8)
                    }

                    if !error.isEmpty {
                        Text(error).foregroundColor(.appLoss).padding(.top, 20)
                    } else if loading {
                        HStack { Spacer(); ProgressView().tint(.appPrimary); Spacer() }.padding(.top, 40)
                    } else if let p = prediction {
                        // Win probability
                        SectionHeader("Win Probability")
                        HStack(spacing: 10) {
                            ProbCard(team: p.team_a, pct: p.prob_a, winning: p.prob_a >= p.prob_b)
                            ProbCard(team: p.team_b, pct: p.prob_b, winning: p.prob_b > p.prob_a)
                        }.padding(.bottom, 4)

                        // Spread
                        SectionHeader(state.sport == .MLB ? "Run Line" : "Spread")
                        spreadCard(p)

                        // Context
                        SectionHeader("Season Record")
                        HStack(spacing: 10) {
                            ContextCard(team: p.team_a, record: p.team_a_record, streak: p.team_a_streak)
                            ContextCard(team: p.team_b, record: p.team_b_record, streak: p.team_b_streak)
                        }

                        // Recent form
                        if let fa = formA, let fb = formB {
                            SectionHeader("Recent Form (Last 5)")
                            HStack(spacing: 10) {
                                FormStrip(team: p.team_a, form: fa)
                                FormStrip(team: p.team_b, form: fb)
                            }
                        }

                        // Injury Report
                        if !injuriesA.isEmpty || !injuriesB.isEmpty {
                            SectionHeader("Injury Report")
                            HStack(alignment: .top, spacing: 10) {
                                InjuryListCard(team: p.team_a, injuries: injuriesA)
                                InjuryListCard(team: p.team_b, injuries: injuriesB)
                            }
                        }

                        // Today's Matchup & Starters
                        if let matchup = todayMatchup {
                            SectionHeader("Today's Matchup")
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text("\(matchup.away_team_full) @ \(matchup.home_team_full)")
                                        .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                                    Spacer()
                                    Text(matchup.status)
                                        .font(.system(size: 11)).foregroundColor(.appPrimary)
                                }
                                if let s = starters, (!s.home.isEmpty || !s.away.isEmpty) {
                                    Text("Confirmed Starters").font(.system(size: 11, weight: .semibold)).foregroundColor(.appSub).padding(.top, 4)
                                    HStack(alignment: .top, spacing: 12) {
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(s.away_team ?? "Away").font(.system(size: 11, weight: .semibold)).foregroundColor(.white)
                                            ForEach(s.away) { p in
                                                Text("\(p.name) (\(p.position))").font(.system(size: 11)).foregroundColor(.appSub)
                                            }
                                        }.frame(maxWidth: .infinity, alignment: .leading)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(s.home_team ?? "Home").font(.system(size: 11, weight: .semibold)).foregroundColor(.white)
                                            ForEach(s.home) { p in
                                                Text("\(p.name) (\(p.position))").font(.system(size: 11)).foregroundColor(.appSub)
                                            }
                                        }.frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                            .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
                        }

                        // H2H Summary
                        if let h = h2h {
                            SectionHeader("Head-to-Head Summary")
                            H2HSummary(teamA: p.team_a, teamB: p.team_b, h2h: h, isMLB: state.sport == .MLB)

                            // H2H Game Log
                            SectionHeader("H2H Game Log")
                            H2HGameLog(games: h.games, teamA: p.team_a, teamB: p.team_b)
                        }

                        // Home / Away
                        if let ha = homeAwayA, let hb = homeAwayB {
                            SectionHeader("Home & Away Performance")
                            HStack(spacing: 10) {
                                HomeAwayCard(team: p.team_a, stats: ha, isMLB: state.sport == .MLB)
                                HomeAwayCard(team: p.team_b, stats: hb, isMLB: state.sport == .MLB)
                            }
                        }

                        // Projected Total (NBA only)
                        if state.sport == .NBA, let proj = projTotal {
                            SectionHeader("Projected Total (O/U)")
                            ProjectedTotalCard(proj: proj, teamA: p.team_a, teamB: p.team_b)
                        }

                    }
                }
                .padding(16)
                .padding(.bottom, 40)
            }
            .refreshable { await load() }
            .background(Color.appBg.ignoresSafeArea())
        }
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: teamA) { _, _ in Task { await load() } }
        .onChange(of: teamB) { _, _ in Task { await load() } }
    }

    @ViewBuilder
    private func spreadCard(_ p: Prediction) -> some View {
        let isMLB = state.sport == .MLB
        Group {
            if p.margin > 0 {
                (Text(p.team_a).foregroundColor(.appPrimary) +
                 Text(" favored by ") +
                 Text(String(format: "%.1f %@", abs(p.margin), isMLB ? "runs" : "pts")).bold())
            } else if p.margin < 0 {
                (Text(p.team_b).foregroundColor(.appPrimary) +
                 Text(" favored by ") +
                 Text(String(format: "%.1f %@", abs(p.margin), isMLB ? "runs" : "pts")).bold())
            } else {
                Text("Pick 'em")
            }
        }
        .font(.system(size: 15))
        .foregroundColor(.appSub)
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.appCard)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.bottom, 4)
    }

    private func loadTeams() async {
        prediction = nil; h2h = nil; homeAwayA = nil; homeAwayB = nil; formA = nil; formB = nil; advancedH2H = nil; projTotal = nil; injuriesA = []; injuriesB = []; todayMatchup = nil; starters = nil
        do {
            teams = try await API.teams(league: state.sport)
            if teams.count >= 2 { teamA = teams[0]; teamB = teams[1] }
        } catch { teams = [] }
        await load()
    }

    private func load() async {
        guard !teamA.isEmpty, !teamB.isEmpty, teamA != teamB else { return }
        loading = true; error = ""
        do {
            async let pred = API.prediction(league: state.sport, teamA: teamA, teamB: teamB)
            async let h2hRes = API.h2h(league: state.sport, teamA: teamA, teamB: teamB)
            async let haA = API.homeAway(league: state.sport, team: teamA)
            async let haB = API.homeAway(league: state.sport, team: teamB)
            async let fA = API.teamForm(league: state.sport, team: teamA, n: 5)
            async let fB = API.teamForm(league: state.sport, team: teamB, n: 5)
            (prediction, h2h, homeAwayA, homeAwayB, formA, formB) = try await (pred, h2hRes, haA, haB, fA, fB)
            // Fetch advanced data + projected total + injuries (NBA only)
            if state.sport == .NBA {
                advancedH2H = try? await API.advancedH2H(teamA: teamA, teamB: teamB)
                projTotal = try? await API.projectedTotal(teamA: teamA, teamB: teamB)
                injuriesA = (try? await API.injuries(league: state.sport, team: teamA)) ?? []
                injuriesB = (try? await API.injuries(league: state.sport, team: teamB)) ?? []

                // Check if these teams play today
                if let allToday = try? await API.todaysGames() {
                    todayMatchup = allToday.first { g in
                        (teamA.contains(g.home_team) || teamA.contains(g.away_team) ||
                         g.home_team_full == teamA || g.away_team_full == teamA) &&
                        (teamB.contains(g.home_team) || teamB.contains(g.away_team) ||
                         g.home_team_full == teamB || g.away_team_full == teamB)
                    }
                    if let matchup = todayMatchup, matchup.game_status >= 2 {
                        starters = try? await API.starters(gameId: matchup.game_id)
                    }
                }
            }
        } catch let e { error = e.localizedDescription }
        loading = false
    }
}

// MARK: - Subviews

private struct SectionHeader: View {
    let title: String
    init(_ t: String) { title = t }
    var body: some View {
        Text(title.uppercased())
            .font(.system(size: 12, weight: .semibold))
            .foregroundColor(.appSub).kerning(0.8)
            .padding(.top, 16).padding(.bottom, 8)
    }
}

private struct ProbCard: View {
    let team: String; let pct: Double; let winning: Bool
    var body: some View {
        VStack(spacing: 4) {
            Text(String(format: "%.0f%%", pct)).font(.system(size: 32, weight: .heavy)).foregroundColor(.white)
            Text(team).font(.system(size: 12)).foregroundColor(.white.opacity(0.9)).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(16)
        .background(winning ? Color.appWin : Color.appLoss)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct ContextCard: View {
    let team: String; let record: TeamRecord; let streak: TeamStreak
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(team).font(.system(size: 13, weight: .semibold)).foregroundColor(.white).lineLimit(2)
            Text("\(record.wins)W – \(record.losses)L").font(.system(size: 12)).foregroundColor(.appSub)
            Text(String(format: "%.0f%% win", record.win_pct)).font(.system(size: 12)).foregroundColor(.appSub)
            Text("\(streak.type)\(streak.count) streak")
                .font(.system(size: 12))
                .foregroundColor(streak.type == "W" ? .appWin : .appLoss)
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(14)
        .background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct FormStrip: View {
    let team: String; let form: TeamForm
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(team).font(.system(size: 12, weight: .semibold)).foregroundColor(.white).lineLimit(1)
            HStack(spacing: 4) {
                ForEach(form.form_log.prefix(5)) { g in
                    VStack(spacing: 2) {
                        Text(g.result).font(.system(size: 12, weight: .bold)).foregroundColor(.white)
                        Text("\(g.scored)-\(g.conceded)").font(.system(size: 9)).foregroundColor(.white.opacity(0.85))
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 6)
                    .background(g.result == "W" ? Color.appWin : Color.appLoss)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
        }
        .frame(maxWidth: .infinity).padding(12)
        .background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct H2HSummary: View {
    let teamA: String; let teamB: String; let h2h: H2HResponse; let isMLB: Bool
    var body: some View {
        VStack(spacing: 0) {
            // Win counts
            HStack(spacing: 10) {
                StatBox(label: "\(teamA) Wins", value: "\(h2h.team_a_wins)", color: .appPrimary)
                StatBox(label: "Avg Total \(isMLB ? "Runs" : "Pts")", value: "\(h2h.avg_total)")
                StatBox(label: "\(teamB) Wins", value: "\(h2h.team_b_wins)", color: .appPrimary)
            }
            .padding(.bottom, 8)

            // Avg scores from games
            let aScores = h2h.games.compactMap { g -> Double? in
                let key = "\(teamA)_score"
                if let v = g[key]?.value { return Double("\(v)") }
                return nil
            }
            let bScores = h2h.games.compactMap { g -> Double? in
                let key = "\(teamB)_score"
                if let v = g[key]?.value { return Double("\(v)") }
                return nil
            }
            if !aScores.isEmpty && !bScores.isEmpty {
                let avgA = aScores.reduce(0, +) / Double(aScores.count)
                let avgB = bScores.reduce(0, +) / Double(bScores.count)
                let margins = zip(aScores, bScores).map { $0 - $1 }
                let avgMarginA = margins.reduce(0, +) / Double(margins.count)

                HStack(spacing: 10) {
                    StatBox(label: "Avg \(isMLB ? "Runs" : "Pts") (\(teamA))", value: String(format: "%.1f", avgA))
                    StatBox(label: "Avg Margin", value: String(format: "%+.1f", avgMarginA))
                    StatBox(label: "Avg \(isMLB ? "Runs" : "Pts") (\(teamB))", value: String(format: "%.1f", avgB))
                }
            }
        }
    }
}

private struct StatBox: View {
    let label: String; let value: String; var color: Color = .white
    var body: some View {
        VStack(spacing: 4) {
            Text(value).font(.system(size: 18, weight: .bold)).foregroundColor(color)
            Text(label).font(.system(size: 10)).foregroundColor(.appSub).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(12)
        .background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct H2HGameLog: View {
    let games: [[String: AnyCodable]]; let teamA: String; let teamB: String

    private func toGame(_ g: [String: AnyCodable]) -> Game? {
        guard let id = g["id"]?.value as? Int,
              let date = g["date"]?.stringValue,
              let league = g["league"]?.stringValue,
              let season = g["season"]?.stringValue else { return nil }
        let aScore = Int(g["\(teamA)_score"]?.stringValue.split(separator: ".").first ?? "0") ?? 0
        let bScore = Int(g["\(teamB)_score"]?.stringValue.split(separator: ".").first ?? "0") ?? 0
        let homeIsA = g["home_team"]?.stringValue == teamA
        return Game(id: id, date: date,
                    home_team: homeIsA ? teamA : teamB,
                    away_team: homeIsA ? teamB : teamA,
                    home_score: homeIsA ? aScore : bScore,
                    away_score: homeIsA ? bScore : aScore,
                    league: league, season: season)
    }

    var body: some View {
        VStack(spacing: 6) {
            ForEach(Array(games.enumerated()), id: \.offset) { _, g in
                let aScore = g["\(teamA)_score"]?.stringValue.split(separator: ".").first.map(String.init) ?? "?"
                let bScore = g["\(teamB)_score"]?.stringValue.split(separator: ".").first.map(String.init) ?? "?"
                let date = g["date"]?.stringValue ?? ""
                let winner = g["winner"]?.stringValue ?? ""
                let row = HStack(spacing: 4) {
                    Text(date).font(.system(size: 11)).foregroundColor(.appSub).frame(width: 76, alignment: .leading)
                    Text(teamA).font(.system(size: 12)).foregroundColor(winner == teamA ? .white : .appSub).lineLimit(1).frame(maxWidth: .infinity, alignment: .trailing)
                    Text("\(aScore)–\(bScore)").font(.system(size: 14, weight: .bold)).foregroundColor(.white).fixedSize().padding(.horizontal, 6)
                    Text(teamB).font(.system(size: 12)).foregroundColor(winner == teamB ? .white : .appSub).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(10).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 8))

                if let game = toGame(g) {
                    NavigationLink(destination: GameDetailView(game: game)) { row }
                } else {
                    row
                }
            }
        }
    }
}

private struct HomeAwayCard: View {
    let team: String; let stats: HomeAwayStats; let isMLB: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(team).font(.system(size: 12, weight: .semibold)).foregroundColor(.white).lineLimit(1)
            ForEach(["Home", "Away"], id: \.self) { loc in
                let s = loc == "Home" ? stats.home : stats.away
                HStack {
                    Text(loc).font(.system(size: 12, weight: .semibold)).foregroundColor(.appSub).frame(width: 36, alignment: .leading)
                    Text(String(format: "%.1f", s.avg_scored)).font(.system(size: 12)).foregroundColor(.white).frame(maxWidth: .infinity)
                    Text(String(format: "%.1f", s.avg_conceded)).font(.system(size: 12)).foregroundColor(.appSub).frame(maxWidth: .infinity)
                    Text(String(format: "%.0f%%", s.win_pct)).font(.system(size: 12)).foregroundColor(s.win_pct >= 50 ? .appWin : .appLoss).frame(maxWidth: .infinity)
                }
            }
            HStack {
                Text("").frame(width: 36)
                Text(isMLB ? "Avg R" : "Avg Pts").font(.system(size: 10)).foregroundColor(.appSub).frame(maxWidth: .infinity)
                Text("Conceded").font(.system(size: 10)).foregroundColor(.appSub).frame(maxWidth: .infinity)
                Text("Win%").font(.system(size: 10)).foregroundColor(.appSub).frame(maxWidth: .infinity)
            }
        }
        .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct InjuryListCard: View {
    let team: String
    let injuries: [Injury]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(team).font(.system(size: 12, weight: .semibold)).foregroundColor(.white).lineLimit(1)
            if injuries.isEmpty {
                Text("All healthy ✅").font(.system(size: 11)).foregroundColor(.appSub)
            } else {
                ForEach(injuries) { inj in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 4) {
                            Text(inj.statusIcon).font(.system(size: 10))
                            Text(inj.player_name).font(.system(size: 12, weight: .semibold)).foregroundColor(.white).lineLimit(1)
                        }
                        Text("\(inj.status)\(inj.injuryDescription.isEmpty ? "" : " — \(inj.injuryDescription)")")
                            .font(.system(size: 10)).foregroundColor(.appSub).lineLimit(2)
                        if let ret = inj.return_date, !ret.isEmpty {
                            Text("Est. return: \(ret)")
                                .font(.system(size: 10)).foregroundColor(.appPrimary)
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct ProjectedTotalCard: View {
    let proj: ProjectedTotalResponse
    let teamA: String
    let teamB: String
    @State private var expanded = false

    private func val(_ step: String, _ key: String) -> String {
        guard let s = proj.steps[step], let v = s[key] else { return "—" }
        return v.stringValue
    }

    private func adj(_ step: String) -> String {
        guard let s = proj.steps[step], let v = s["adjustment"] else { return "—" }
        let n = Double(v.stringValue) ?? 0
        return String(format: "%+.1f", n)
    }

    var body: some View {
        VStack(spacing: 12) {
            // Big projected total
            VStack(spacing: 4) {
                Text(String(format: "%.1f", proj.projected_total))
                    .font(.system(size: 42, weight: .bold))
                    .foregroundColor(Color(hex: "#6c5ce7"))
                Text("Projected Game Total")
                    .font(.system(size: 12)).foregroundColor(.appSub)
            }
            .frame(maxWidth: .infinity)
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color(hex: "#6c5ce7"), lineWidth: 2)
                    .background(Color.appCard.clipShape(RoundedRectangle(cornerRadius: 10)))
            )

            // Expandable breakdown
            Button { withAnimation { expanded.toggle() } } label: {
                HStack {
                    Text("Step-by-step breakdown")
                        .font(.system(size: 13, weight: .semibold)).foregroundColor(.white)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 12)).foregroundColor(.appSub)
                }
                .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 8))
            }

            if expanded {
                VStack(alignment: .leading, spacing: 10) {
                    stepRow("1. Base Total", detail: "Pace: \(val("step_1_base","pace_a"))/\(val("step_1_base","pace_b")) → Poss: \(val("step_1_base","expected_possessions"))", value: val("step_1_base", "base_total"))
                    stepRow("2. Shooting", detail: "eFG%: \(val("step_2_shooting","efg_a"))% / \(val("step_2_shooting","efg_b"))%", value: adj("step_2_shooting"))
                    stepRow("3. Turnovers", detail: "TOV%: \(val("step_3_turnovers","tov_rate_a"))% / \(val("step_3_turnovers","tov_rate_b"))%", value: adj("step_3_turnovers"))
                    stepRow("4. Free Throws", detail: "FTr: \(val("step_4_free_throws","ft_rate_a"))% / \(val("step_4_free_throws","ft_rate_b"))%", value: adj("step_4_free_throws"))
                    stepRow("5. Rest", detail: "\(val("step_5_rest","rest_days_a"))d / \(val("step_5_rest","rest_days_b"))d", value: adj("step_5_rest"))
                    stepRow("6. Home Court", detail: val("step_6_home_court", "home_team"), value: adj("step_6_home_court"))
                    stepRow("7. Form", detail: "Δ \(val("step_7_form","form_delta_a")) / \(val("step_7_form","form_delta_b"))", value: adj("step_7_form"))
                    stepRow("8. Injuries", detail: injuryStepDetail(), value: adj("step_8_injuries"))

                    Divider().background(Color.appBorder)

                    HStack {
                        Text("Final").font(.system(size: 13, weight: .bold)).foregroundColor(.white)
                        Spacer()
                        Text(String(format: "%.1f", proj.projected_total))
                            .font(.system(size: 15, weight: .bold))
                            .foregroundColor(Color(hex: "#6c5ce7"))
                    }
                }
                .padding(12).background(Color.appCard).clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
    }

    private func injuryStepDetail() -> String {
        guard let s = proj.steps["step_8_injuries"] else { return "No data" }
        if s["skipped"]?.stringValue == "true" || s["skipped"]?.stringValue == "1" {
            return "No injury data — refresh from sidebar"
        }
        let countA = (s["injured_out_a"]?.value as? [[String: Any]])?.count ?? 0
        let countB = (s["injured_out_b"]?.value as? [[String: Any]])?.count ?? 0
        if countA == 0 && countB == 0 { return "No key players Out/Doubtful" }
        return "\(countA) out (\(teamA)) / \(countB) out (\(teamB))"
    }

    @ViewBuilder
    private func stepRow(_ title: String, detail: String, value: String) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 12, weight: .semibold)).foregroundColor(.white)
                Text(detail).font(.system(size: 11)).foregroundColor(.appSub)
            }
            Spacer()
            Text(value)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(value.hasPrefix("+") ? .appWin : value.hasPrefix("-") ? .appLoss : .white)
        }
    }
}
