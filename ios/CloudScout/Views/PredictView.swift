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
    @State private var projTotal: ProjectedTotalResponse?
    @State private var injuriesA: [Injury] = []
    @State private var injuriesB: [Injury] = []
    @State private var todayMatchup: TodayGame?
    @State private var starters: StartersResponse?
    @State private var loading = false
    @State private var error = ""
    @State private var loadTeamsTask: Task<Void, Never>?
    @State private var showBreakdown = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color.csBg.ignoresSafeArea()
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        header
                            .padding(.horizontal, 18)
                            .padding(.top, 4)

                        SportToggle(sport: $state.sport)
                            .padding(.horizontal, 16)

                        matchupPicker
                            .padding(.horizontal, 14)

                        if teamA == teamB && !teamA.isEmpty {
                            Text("Select two different teams.")
                                .font(.system(size: 13))
                                .foregroundColor(.csLoss)
                                .padding(.horizontal, 16)
                        }

                        if !error.isEmpty {
                            Text(error)
                                .foregroundColor(.csLive)
                                .padding(.horizontal, 16)
                                .padding(.top, 20)
                        } else if loading && prediction == nil {
                            HStack { Spacer(); ProgressView().tint(.csNBA); Spacer() }
                                .padding(.top, 40)
                        } else if let p = prediction {
                            winProbabilitySection(p)

                            if state.sport == .MLB, p.proj_runs_a != nil {
                                mlbProjectedScoreSection(p)
                            }

                            factorsSection(p)

                            if state.sport == .MLB, let pillars = p.pillars, !pillars.isEmpty {
                                mlbPillarsSection(p: p, pillars: pillars)
                            }

                            if state.sport == .NBA, let matchup = todayMatchup {
                                todayMatchupSection(matchup)
                            }

                            if let fa = formA, let fb = formB {
                                recentFormSection(p: p, fa: fa, fb: fb)
                            }

                            seasonRecordSection(p)

                            if state.sport == .NBA, !injuriesA.isEmpty || !injuriesB.isEmpty {
                                injuryReportSection(p)
                            }

                            if let h = h2h {
                                h2hSummarySection(p: p, h2h: h)
                                if !h.games.isEmpty {
                                    h2hGameLogSection(p: p, h2h: h)
                                }
                            }

                            if let ha = homeAwayA, let hb = homeAwayB {
                                homeAwaySection(p: p, ha: ha, hb: hb)
                            }

                            if state.sport == .NBA, let proj = projTotal {
                                projectedTotalSection(proj)
                            }
                        }

                        Spacer(minLength: 30)
                    }
                    .padding(.bottom, 40)
                }
                .refreshable { await load() }
            }
            .toolbarBackground(Color.csBg, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.light)
        .task { startLoadTeams() }
        .onChange(of: state.sport) { _, _ in startLoadTeams() }
        .onChange(of: state.pendingPredictMatchup) { _, new in
            if new != nil { startLoadTeams() }
        }
        .onChange(of: teamA) { _, _ in Task { await load() } }
        .onChange(of: teamB) { _, _ in Task { await load() } }
    }

    // MARK: - Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("MATCHUP")
                .font(.csSection)
                .kerning(1.0)
                .foregroundColor(.csSub)
            Text("Predict")
                .font(.csEditorial(40))
                .foregroundColor(.csText)
        }
    }

    // MARK: - Matchup picker

    private var matchupPicker: some View {
        HStack(spacing: 12) {
            MatchupSlot(team: teamA, league: state.sport.rawValue, teams: teams, selection: $teamA)
            Text("VS")
                .font(.system(size: 14, weight: .heavy))
                .foregroundColor(.csFaint)
            MatchupSlot(team: teamB, league: state.sport.rawValue, teams: teams, selection: $teamB)
        }
        .padding(14)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    // MARK: - Win probability

    @ViewBuilder
    private func winProbabilitySection(_ p: Prediction) -> some View {
        SectionHeader(title: "Win Probability")
            .padding(.horizontal, 16)

        let probA = p.prob_a
        let probB = p.prob_b
        let aLeads = probA >= probB
        let colorA = TeamStyle.lookup(p.team_a, league: state.sport.rawValue).color
        let colorB = TeamStyle.lookup(p.team_b, league: state.sport.rawValue).color

        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .bottom, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        TeamBadge(team: p.team_a, league: state.sport.rawValue, size: 26)
                        Text(TeamStyle.nickname(for: p.team_a, league: state.sport.rawValue))
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(.csText)
                            .lineLimit(1)
                    }
                    Text(String(format: "%.0f%%", probA))
                        .font(.csMono(aLeads ? 44 : 34, weight: aLeads ? .heavy : .bold))
                        .foregroundColor(aLeads ? .csWin : .csSub)
                        .monospacedDigit()
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                VStack(alignment: .trailing, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(TeamStyle.nickname(for: p.team_b, league: state.sport.rawValue))
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(aLeads ? .csSub : .csText)
                            .lineLimit(1)
                        TeamBadge(team: p.team_b, league: state.sport.rawValue, size: 26)
                    }
                    Text(String(format: "%.0f%%", probB))
                        .font(.csMono(aLeads ? 34 : 44, weight: aLeads ? .bold : .heavy))
                        .foregroundColor(aLeads ? .csSub : .csWin)
                        .monospacedDigit()
                }
                .frame(maxWidth: .infinity, alignment: .trailing)
            }

            probabilityBar(probA: probA, probB: probB, colorA: colorA, colorB: colorB)

            spreadChip(p)
        }
        .csCard(radius: 18, padding: EdgeInsets(top: 18, leading: 18, bottom: 18, trailing: 18))
        .padding(.horizontal, 14)
    }

    private func probabilityBar(probA: Double, probB: Double, colorA: Color, colorB: Color) -> some View {
        GeometryReader { geo in
            let total = max(probA + probB, 1)
            let aW = geo.size.width * probA / total
            HStack(spacing: 0) {
                Rectangle().fill(colorA).frame(width: aW)
                Rectangle().fill(colorB)
            }
            .clipShape(Capsule())
        }
        .frame(height: 10)
        .background(Capsule().fill(Color.csChip))
    }

    @ViewBuilder
    private func spreadChip(_ p: Prediction) -> some View {
        let isMLB = state.sport == .MLB
        let unit = isMLB ? "runs" : "pts"
        let favorite = p.margin > 0 ? p.team_a : (p.margin < 0 ? p.team_b : "")
        let favColor = favorite.isEmpty ? Color.csText : TeamStyle.lookup(favorite, league: state.sport.rawValue).color
        HStack(spacing: 10) {
            Text("SPREAD")
                .font(.csSection)
                .kerning(0.6)
                .foregroundColor(.csSub)
            Group {
                if p.margin == 0 {
                    Text("Pick 'em").foregroundColor(.csText)
                } else {
                    HStack(spacing: 4) {
                        Text(TeamStyle.nickname(for: favorite, league: state.sport.rawValue))
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(favColor)
                        Text("favored by")
                            .font(.system(size: 14))
                            .foregroundColor(.csText)
                        Text(String(format: "%.1f", abs(p.margin)))
                            .font(.csMono(14, weight: .heavy))
                            .foregroundColor(.csText)
                        Text(unit)
                            .font(.system(size: 14))
                            .foregroundColor(.csText)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.csChip)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    // MARK: - Factors

    @ViewBuilder
    private func factorsSection(_ p: Prediction) -> some View {
        SectionHeader(title: "Why · Factors")
            .padding(.horizontal, 16)

        let rows = buildFactorRows(p)
        let colorA = TeamStyle.lookup(p.team_a, league: state.sport.rawValue).color
        let colorB = TeamStyle.lookup(p.team_b, league: state.sport.rawValue).color

        VStack(spacing: 8) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                FactorRow(label: row.label, valueA: row.valueA, valueB: row.valueB, lean: row.lean, colorA: colorA, colorB: colorB)
            }
        }
        .padding(.horizontal, 14)
    }

    private struct FactorRowData {
        let label: String
        let valueA: String
        let valueB: String
        let lean: Double  // -1..+1, positive = team A
    }

    private func buildFactorRows(_ p: Prediction) -> [FactorRowData] {
        var rows: [FactorRowData] = []
        let isMLB = state.sport == .MLB
        let unit = isMLB ? "R" : "pts"

        // Overall record
        let recA = "\(p.team_a_record.wins)-\(p.team_a_record.losses)"
        let recB = "\(p.team_b_record.wins)-\(p.team_b_record.losses)"
        let pctDiff = (p.team_a_record.win_pct - p.team_b_record.win_pct) / 100
        rows.append(.init(label: "Overall record", valueA: recA, valueB: recB, lean: clamp(pctDiff * 2)))

        // Net rating / run diff
        if let fa = formA, let fb = formB {
            let nA = String(format: "%+.1f", fa.net_rating)
            let nB = String(format: "%+.1f", fb.net_rating)
            let diff = fa.net_rating - fb.net_rating
            let span = isMLB ? 4.0 : 10.0
            rows.append(.init(label: isMLB ? "Run differential" : "Net rating", valueA: nA, valueB: nB, lean: clamp(diff / span)))
        }

        // Home/away split
        if let ha = homeAwayA, let hb = homeAwayB {
            let haStr = "\(ha.home.games > 0 ? String(format: "%.0f%% H", ha.home.win_pct) : "—")"
            let hbStr = "\(hb.away.games > 0 ? String(format: "%.0f%% A", hb.away.win_pct) : "—")"
            let diff = (ha.home.win_pct - hb.away.win_pct) / 100
            rows.append(.init(label: "Home / away split", valueA: haStr, valueB: hbStr, lean: clamp(diff * 1.5)))
        }

        // H2H
        if let h = h2h, h.team_a_wins + h.team_b_wins > 0 {
            let total = h.team_a_wins + h.team_b_wins
            let lean = Double(h.team_a_wins - h.team_b_wins) / Double(total)
            rows.append(.init(label: "Head-to-head", valueA: "\(h.team_a_wins)-\(h.team_b_wins)", valueB: "\(h.team_b_wins)-\(h.team_a_wins)", lean: lean))
        }

        // Streaks
        let streakA = p.team_a_streak.type == "W" ? p.team_a_streak.count : -p.team_a_streak.count
        let streakB = p.team_b_streak.type == "W" ? p.team_b_streak.count : -p.team_b_streak.count
        let streakLean = clamp(Double(streakA - streakB) / 6.0)
        let streakAStr = "\(p.team_a_streak.type)\(p.team_a_streak.count)"
        let streakBStr = "\(p.team_b_streak.type)\(p.team_b_streak.count)"
        rows.append(.init(label: "Current streak", valueA: streakAStr, valueB: streakBStr, lean: streakLean))

        // Injuries (NBA only)
        if state.sport == .NBA, !injuriesA.isEmpty || !injuriesB.isEmpty {
            let outsA = injuriesA.filter { $0.status.lowercased() == "out" || $0.status.lowercased() == "doubtful" }.count
            let outsB = injuriesB.filter { $0.status.lowercased() == "out" || $0.status.lowercased() == "doubtful" }.count
            let lean = clamp(Double(outsB - outsA) / 4.0)
            rows.append(.init(label: "Key injuries", valueA: "\(outsA)", valueB: "\(outsB)", lean: lean))
        }

        _ = unit
        return rows
    }

    private func clamp(_ x: Double) -> Double { min(1.0, max(-1.0, x)) }

    // MARK: - MLB projected score

    @ViewBuilder
    private func mlbProjectedScoreSection(_ p: Prediction) -> some View {
        if let runsA = p.proj_runs_a, let runsB = p.proj_runs_b {
            let colorA = TeamStyle.lookup(p.team_a, league: state.sport.rawValue).color
            let colorB = TeamStyle.lookup(p.team_b, league: state.sport.rawValue).color
            let aLeads = runsA >= runsB

            SectionHeader(title: "Projected Score")
                .padding(.horizontal, 16)

            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            TeamBadge(team: p.team_a, league: state.sport.rawValue, size: 22)
                            Text(TeamStyle.lookup(p.team_a, league: state.sport.rawValue).abbr)
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundColor(.csSub)
                        }
                        Text(String(format: "%.1f", runsA))
                            .font(.csMono(36, weight: .heavy))
                            .foregroundColor(aLeads ? colorA : .csText)
                            .monospacedDigit()
                    }
                    Spacer()
                    Text("–")
                        .font(.csMono(28, weight: .bold))
                        .foregroundColor(.csFaint)
                    Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        HStack(spacing: 6) {
                            Text(TeamStyle.lookup(p.team_b, league: state.sport.rawValue).abbr)
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundColor(.csSub)
                            TeamBadge(team: p.team_b, league: state.sport.rawValue, size: 22)
                        }
                        Text(String(format: "%.1f", runsB))
                            .font(.csMono(36, weight: .heavy))
                            .foregroundColor(aLeads ? .csText : colorB)
                            .monospacedDigit()
                    }
                }

                Divider().background(Color.csBorder)

                HStack(spacing: 14) {
                    if let total = p.projected_total {
                        miniStat(label: "TOTAL", value: String(format: "%.1f", total))
                    }
                    if let pyth = p.pythagorean_prob_a {
                        miniStat(
                            label: "PYTHAG",
                            value: "\(Int(pyth.rounded()))% / \(Int((100 - pyth).rounded()))%"
                        )
                    }
                    if let h2hAvg = p.h2h_avg_total {
                        miniStat(label: "H2H AVG", value: String(format: "%.1f", h2hAvg))
                    }
                }
            }
            .csCard(radius: 16, padding: EdgeInsets(top: 16, leading: 18, bottom: 16, trailing: 18))
            .padding(.horizontal, 14)
        }
    }

    @ViewBuilder
    private func miniStat(label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 9, weight: .heavy))
                .kerning(0.6)
                .foregroundColor(.csFaint)
            Text(value)
                .font(.csMono(13, weight: .bold))
                .foregroundColor(.csText)
                .monospacedDigit()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - MLB 8-pillar breakdown

    @ViewBuilder
    private func mlbPillarsSection(p: Prediction, pillars: [PredictionPillar]) -> some View {
        SectionHeader(title: "8-Pillar Scout Model")
            .padding(.horizontal, 16)

        let colorA = TeamStyle.lookup(p.team_a, league: state.sport.rawValue).color
        let colorB = TeamStyle.lookup(p.team_b, league: state.sport.rawValue).color

        VStack(spacing: 8) {
            ForEach(Array(pillars.enumerated()), id: \.offset) { _, pl in
                let edge = pl.score_a - pl.score_b   // -1..+1 already since each [0,1]
                let lean = max(-1.0, min(1.0, edge * 2.0))
                FactorRow(
                    label: "\(pl.name)  ·  \(Int((pl.weight * 100).rounded()))%",
                    valueA: String(format: "%.2f", pl.score_a),
                    valueB: String(format: "%.2f", pl.score_b),
                    lean: lean,
                    colorA: colorA,
                    colorB: colorB
                )
            }
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Projected total

    @ViewBuilder
    private func projectedTotalSection(_ proj: ProjectedTotalResponse) -> some View {
        let purple = Color(hex: "6c5ce7")
        SectionHeader(title: "Projected Total (O/U)")
            .padding(.horizontal, 16)

        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(String(format: "%.1f", proj.projected_total))
                    .font(.csMono(42, weight: .heavy))
                    .foregroundColor(purple)
                    .monospacedDigit()
                Text("projected total")
                    .font(.system(size: 12))
                    .foregroundColor(.csSub)
            }

            HStack {
                Text(baseAdjustmentText(proj))
                    .font(.system(size: 12))
                    .foregroundColor(.csSub)
                Spacer()
                Button {
                    withAnimation { showBreakdown.toggle() }
                } label: {
                    HStack(spacing: 3) {
                        Text("Step-by-step")
                        Image(systemName: showBreakdown ? "chevron.up" : "chevron.right")
                    }
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.csNBA)
                }
                .buttonStyle(.plain)
            }

            if showBreakdown {
                Divider().background(Color.csBorder)
                breakdownRows(proj)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 18, style: .continuous).fill(Color.csCard)
                Rectangle().fill(purple).frame(width: 4).clipShape(
                    UnevenRoundedRectangle(cornerRadii: .init(topLeading: 18, bottomLeading: 18), style: .continuous)
                )
            }
        )
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .padding(.horizontal, 14)
    }

    private func baseAdjustmentText(_ proj: ProjectedTotalResponse) -> String {
        let base = Double(proj.steps["step_1_base"]?["base_total"]?.stringValue ?? "0") ?? 0
        let adj = proj.projected_total - base
        return String(format: "Base %.1f · Adjustments %+.1f", base, adj)
    }

    @ViewBuilder
    private func breakdownRows(_ proj: ProjectedTotalResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            breakdownRow("Shooting", key: "step_2_shooting")
            breakdownRow("Turnovers", key: "step_3_turnovers")
            breakdownRow("Free throws", key: "step_4_free_throws")
            breakdownRow("Rest", key: "step_5_rest")
            breakdownRow("Home court", key: "step_6_home_court")
            breakdownRow("Form", key: "step_7_form")
            breakdownRow("Injuries", key: "step_8_injuries")
        }
    }

    @ViewBuilder
    private func breakdownRow(_ label: String, key: String) -> some View {
        let adjStr = proj_adj(key)
        HStack {
            Text(label).font(.system(size: 13)).foregroundColor(.csText)
            Spacer()
            Text(adjStr)
                .font(.csMono(13, weight: .bold))
                .foregroundColor(adjStr.hasPrefix("+") ? .csWin : adjStr.hasPrefix("-") ? .csLoss : .csSub)
                .monospacedDigit()
        }
    }

    private func proj_adj(_ key: String) -> String {
        guard let proj = projTotal, let v = proj.steps[key]?["adjustment"] else { return "—" }
        let n = Double(v.stringValue) ?? 0
        return String(format: "%+.1f", n)
    }

    // MARK: - Today's matchup + starters

    @ViewBuilder
    private func todayMatchupSection(_ matchup: TodayGame) -> some View {
        SectionHeader(title: "Today's Matchup")
            .padding(.horizontal, 16)

        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                TeamBadge(team: matchup.away_team_full, league: "NBA", size: 36)
                Text(TeamStyle.nickname(for: matchup.away_team_full, league: "NBA"))
                    .font(.csEditorial(20))
                    .foregroundColor(.csText)
                Text("@")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.csFaint)
                Text(TeamStyle.nickname(for: matchup.home_team_full, league: "NBA"))
                    .font(.csEditorial(20))
                    .foregroundColor(.csText)
                TeamBadge(team: matchup.home_team_full, league: "NBA", size: 36)
                Spacer(minLength: 0)
                if matchup.game_status == 2 {
                    StatusPill(kind: .live, text: "Live")
                } else if matchup.game_status == 3 {
                    StatusPill(kind: .final, text: "Final")
                } else {
                    StatusPill(kind: .scheduled, text: matchup.status)
                }
            }

            if let s = starters, (!s.home.isEmpty || !s.away.isEmpty) {
                Divider().background(Color.csBorder)
                Text("CONFIRMED STARTERS")
                    .font(.csSection)
                    .kerning(0.8)
                    .foregroundColor(.csSub)
                HStack(alignment: .top, spacing: 14) {
                    starterColumn(team: s.away_team ?? matchup.away_team_full, players: s.away)
                    Divider().background(Color.csBorder)
                    starterColumn(team: s.home_team ?? matchup.home_team_full, players: s.home)
                }
            }
        }
        .csCard(radius: 16)
        .padding(.horizontal, 14)
    }

    @ViewBuilder
    private func starterColumn(team: String, players: [StarterPlayer]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(TeamStyle.nickname(for: team, league: "NBA"))
                .font(.system(size: 12, weight: .heavy))
                .kerning(0.5)
                .foregroundColor(.csText)
            ForEach(players) { p in
                HStack(spacing: 6) {
                    Text(p.position)
                        .font(.csMono(10, weight: .heavy))
                        .foregroundColor(.csSub)
                        .frame(width: 22, alignment: .leading)
                    Text(p.name)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.csText)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Recent form

    @ViewBuilder
    private func recentFormSection(p: Prediction, fa: TeamForm, fb: TeamForm) -> some View {
        SectionHeader(title: "Recent Form · Last 5")
            .padding(.horizontal, 16)

        HStack(spacing: 10) {
            FormStripCard(team: p.team_a, league: state.sport.rawValue, form: fa)
            FormStripCard(team: p.team_b, league: state.sport.rawValue, form: fb)
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Season record

    @ViewBuilder
    private func seasonRecordSection(_ p: Prediction) -> some View {
        SectionHeader(title: "Season Record")
            .padding(.horizontal, 16)

        HStack(spacing: 10) {
            RecordCard(team: p.team_a, league: state.sport.rawValue, record: p.team_a_record, streak: p.team_a_streak)
            RecordCard(team: p.team_b, league: state.sport.rawValue, record: p.team_b_record, streak: p.team_b_streak)
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Injury report

    @ViewBuilder
    private func injuryReportSection(_ p: Prediction) -> some View {
        SectionHeader(title: "Injury Report")
            .padding(.horizontal, 16)

        VStack(spacing: 10) {
            InjurySummaryCard(team: p.team_a, league: state.sport.rawValue, injuries: injuriesA)
            InjurySummaryCard(team: p.team_b, league: state.sport.rawValue, injuries: injuriesB)
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Head-to-head

    @ViewBuilder
    private func h2hSummarySection(p: Prediction, h2h: H2HResponse) -> some View {
        SectionHeader(title: "Head-to-Head")
            .padding(.horizontal, 16)

        let isMLB = state.sport == .MLB
        let unit = isMLB ? "RUNS" : "PTS"
        let aColor = TeamStyle.lookup(p.team_a, league: state.sport.rawValue).color
        let bColor = TeamStyle.lookup(p.team_b, league: state.sport.rawValue).color

        VStack(spacing: 10) {
            HStack(spacing: 8) {
                StatBox(value: "\(h2h.team_a_wins)", label: "\(TeamStyle.lookup(p.team_a, league: state.sport.rawValue).abbr) WINS", accent: aColor)
                StatBox(value: String(format: "%.1f", h2h.avg_total), label: "AVG TOTAL \(unit)")
                StatBox(value: "\(h2h.team_b_wins)", label: "\(TeamStyle.lookup(p.team_b, league: state.sport.rawValue).abbr) WINS", accent: bColor)
            }

            let aScores = h2h.games.compactMap { g -> Double? in
                guard let v = g["\(p.team_a)_score"]?.value else { return nil }
                return Double("\(v)")
            }
            let bScores = h2h.games.compactMap { g -> Double? in
                guard let v = g["\(p.team_b)_score"]?.value else { return nil }
                return Double("\(v)")
            }
            if !aScores.isEmpty, aScores.count == bScores.count {
                let avgA = aScores.reduce(0, +) / Double(aScores.count)
                let avgB = bScores.reduce(0, +) / Double(bScores.count)
                let avgMargin = (avgA - avgB)
                HStack(spacing: 8) {
                    StatBox(value: String(format: "%.1f", avgA), label: "\(TeamStyle.lookup(p.team_a, league: state.sport.rawValue).abbr) AVG")
                    StatBox(value: String(format: "%+.1f", avgMargin), label: "MARGIN", accent: avgMargin >= 0 ? .csWin : .csLoss)
                    StatBox(value: String(format: "%.1f", avgB), label: "\(TeamStyle.lookup(p.team_b, league: state.sport.rawValue).abbr) AVG")
                }
            }
        }
        .padding(.horizontal, 14)
    }

    @ViewBuilder
    private func h2hGameLogSection(p: Prediction, h2h: H2HResponse) -> some View {
        SectionHeader(title: "H2H Game Log")
            .padding(.horizontal, 16)

        VStack(spacing: 6) {
            ForEach(Array(h2h.games.enumerated()), id: \.offset) { _, g in
                H2HGameRow(raw: g, teamA: p.team_a, teamB: p.team_b, league: state.sport.rawValue)
            }
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Home & away

    @ViewBuilder
    private func homeAwaySection(p: Prediction, ha: HomeAwayStats, hb: HomeAwayStats) -> some View {
        SectionHeader(title: "Home & Away Performance")
            .padding(.horizontal, 16)

        HStack(spacing: 10) {
            HomeAwaySplitCard(team: p.team_a, league: state.sport.rawValue, stats: ha, isMLB: state.sport == .MLB)
            HomeAwaySplitCard(team: p.team_b, league: state.sport.rawValue, stats: hb, isMLB: state.sport == .MLB)
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Data

    private func startLoadTeams() {
        loadTeamsTask?.cancel()
        loadTeamsTask = Task { await loadTeams() }
    }

    private func loadTeams() async {
        prediction = nil; h2h = nil; homeAwayA = nil; homeAwayB = nil
        formA = nil; formB = nil; projTotal = nil
        injuriesA = []; injuriesB = []
        todayMatchup = nil; starters = nil
        let league = state.sport
        let fetched = (try? await API.teams(league: league)) ?? []
        guard !Task.isCancelled else { return }
        teams = fetched
        if let pending = state.pendingPredictMatchup, pending.sport == league {
            teamA = pending.homeTeam
            teamB = pending.awayTeam
            state.pendingPredictMatchup = nil
        } else if teams.count >= 2 {
            teamA = teams[0]; teamB = teams[1]
        }
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
            if state.sport == .NBA {
                projTotal = try? await API.projectedTotal(teamA: teamA, teamB: teamB)
                injuriesA = (try? await API.injuries(league: state.sport, team: teamA)) ?? []
                injuriesB = (try? await API.injuries(league: state.sport, team: teamB)) ?? []

                if let allToday = try? await API.todaysGames() {
                    todayMatchup = allToday.first { g in
                        let aMatches = teamA.contains(g.home_team) || teamA.contains(g.away_team) ||
                            g.home_team_full == teamA || g.away_team_full == teamA
                        let bMatches = teamB.contains(g.home_team) || teamB.contains(g.away_team) ||
                            g.home_team_full == teamB || g.away_team_full == teamB
                        return aMatches && bMatches
                    }
                    if let matchup = todayMatchup, matchup.game_status >= 2 {
                        starters = try? await API.starters(gameId: matchup.game_id)
                    } else {
                        starters = nil
                    }
                } else {
                    todayMatchup = nil
                    starters = nil
                }
            } else {
                todayMatchup = nil
                starters = nil
            }
        } catch let e { error = e.localizedDescription }
        loading = false
    }
}

// MARK: - Matchup slot

private struct MatchupSlot: View {
    let team: String
    let league: String
    let teams: [String]
    @Binding var selection: String

    var body: some View {
        Menu {
            ForEach(teams, id: \.self) { t in
                Button(t) { selection = t }
            }
        } label: {
            HStack(spacing: 8) {
                TeamBadge(team: team.isEmpty ? "TBD" : team, league: league, size: 32)
                VStack(alignment: .leading, spacing: 1) {
                    Text(league.uppercased())
                        .font(.system(size: 10, weight: .heavy))
                        .kerning(0.5)
                        .foregroundColor(.csFaint)
                    Text(team.isEmpty ? "Select" : TeamStyle.nickname(for: team, league: league))
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(.csText)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.down")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(.csFaint)
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(Color.csChip)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Factor row

private struct FactorRow: View {
    let label: String
    let valueA: String
    let valueB: String
    let lean: Double
    let colorA: Color
    let colorB: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(.csSub)
            HStack(spacing: 10) {
                Text(valueA)
                    .font(.csMono(13, weight: .bold))
                    .foregroundColor(.csText)
                    .frame(width: 76, alignment: .leading)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                FactorBar(lean: lean, colorA: colorA, colorB: colorB)
                    .frame(height: 6)
                Text(valueB)
                    .font(.csMono(13, weight: .semibold))
                    .foregroundColor(.csSub)
                    .frame(width: 76, alignment: .trailing)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Form strip card

private struct FormStripCard: View {
    let team: String
    let league: String
    let form: TeamForm

    private func gameFrom(_ g: FormGame) -> Game {
        let isHome = g.location.lowercased() == "home"
        let season = String(Calendar.current.component(.year, from: Date()))
        return Game(
            id: abs((g.date + g.opponent).hashValue),
            date: g.date,
            home_team: isHome ? team : g.opponent,
            away_team: isHome ? g.opponent : team,
            home_score: isHome ? g.scored : g.conceded,
            away_score: isHome ? g.conceded : g.scored,
            league: league,
            season: season
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                TeamBadge(team: team, league: league, size: 24)
                Text(TeamStyle.nickname(for: team, league: league))
                    .font(.system(size: 12, weight: .heavy))
                    .kerning(0.4)
                    .foregroundColor(.csText)
                    .lineLimit(1)
            }
            HStack(spacing: 5) {
                ForEach(form.form_log.prefix(5)) { g in
                    NavigationLink {
                        GameDetailView(game: gameFrom(g), selectedTeam: team)
                    } label: {
                        VStack(spacing: 2) {
                            Text(g.result)
                                .font(.system(size: 13, weight: .heavy))
                                .foregroundColor(.white)
                            Text(String(format: "%+d", g.margin))
                                .font(.csMono(11, weight: .bold))
                                .foregroundColor(.white.opacity(0.9))
                                .monospacedDigit()
                                .lineLimit(1)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(g.result == "W" ? Color.csWin : Color.csLoss)
                        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Record card

private struct RecordCard: View {
    let team: String
    let league: String
    let record: TeamRecord
    let streak: TeamStreak

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                TeamBadge(team: team, league: league, size: 24)
                Text(TeamStyle.nickname(for: team, league: league))
                    .font(.system(size: 12, weight: .heavy))
                    .kerning(0.4)
                    .foregroundColor(.csText)
                    .lineLimit(1)
            }
            Text("\(record.wins)–\(record.losses)")
                .font(.csMono(28, weight: .heavy))
                .foregroundColor(.csText)
                .monospacedDigit()
            HStack(spacing: 8) {
                Text(String(format: "%.0f%% win", record.win_pct))
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.csSub)
                Text("·").foregroundColor(.csFaint)
                Text("\(streak.type)\(streak.count)")
                    .font(.csMono(11, weight: .heavy))
                    .foregroundColor(streak.type == "W" ? .csWin : .csLoss)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Injury summary card

private struct InjurySummaryCard: View {
    let team: String
    let league: String
    let injuries: [Injury]

    private func kind(_ status: String) -> StatusPill.Kind? {
        switch status.lowercased() {
        case "out": return .out
        case "doubtful": return .doubtful
        case "questionable", "day-to-day": return .questionable
        default: return nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                TeamBadge(team: team, league: league, size: 24)
                Text(TeamStyle.nickname(for: team, league: league))
                    .font(.system(size: 12, weight: .heavy))
                    .kerning(0.4)
                    .foregroundColor(.csText)
                Spacer(minLength: 0)
                Text("\(injuries.count)")
                    .font(.system(size: 11, weight: .heavy))
                    .foregroundColor(.csSub)
                    .padding(.horizontal, 9).padding(.vertical, 3)
                    .background(Color.csChip)
                    .clipShape(Capsule())
            }

            if injuries.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 13))
                        .foregroundColor(.csWin)
                    Text("All healthy")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.csSub)
                }
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(injuries.prefix(4)) { inj in
                        HStack(spacing: 8) {
                            Text(inj.player_name)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(.csText)
                                .lineLimit(1)
                            Spacer(minLength: 4)
                            if let k = kind(inj.status) {
                                StatusPill(kind: k, text: inj.status)
                            }
                        }
                    }
                    if injuries.count > 4 {
                        Text("+\(injuries.count - 4) more")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.csSub)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - H2H game row

private struct H2HGameRow: View {
    let raw: [String: AnyCodable]
    let teamA: String
    let teamB: String
    let league: String

    private var aScore: Int {
        Int(raw["\(teamA)_score"]?.stringValue.split(separator: ".").first.map(String.init) ?? "") ?? 0
    }
    private var bScore: Int {
        Int(raw["\(teamB)_score"]?.stringValue.split(separator: ".").first.map(String.init) ?? "") ?? 0
    }
    private var date: String { raw["date"]?.stringValue ?? "" }
    private var winner: String { raw["winner"]?.stringValue ?? "" }

    private func toGame() -> Game? {
        guard let id = raw["id"]?.value as? Int,
              let season = raw["season"]?.stringValue else { return nil }
        let homeIsA = raw["home_team"]?.stringValue == teamA
        return Game(
            id: id, date: date,
            home_team: homeIsA ? teamA : teamB,
            away_team: homeIsA ? teamB : teamA,
            home_score: homeIsA ? aScore : bScore,
            away_score: homeIsA ? bScore : aScore,
            league: league, season: season
        )
    }

    private var formattedDate: String {
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        guard let d = inFmt.date(from: date) else { return date }
        let out = DateFormatter()
        out.dateFormat = "MMM d"
        return out.string(from: d)
    }

    @ViewBuilder
    private var rowContent: some View {
        HStack(spacing: 8) {
            Text(formattedDate)
                .font(.csMono(11, weight: .semibold))
                .foregroundColor(.csSub)
                .frame(width: 56, alignment: .leading)
            Text(TeamStyle.lookup(teamA, league: league).abbr)
                .font(.system(size: 12, weight: winner == teamA ? .heavy : .semibold))
                .foregroundColor(winner == teamA ? .csText : .csSub)
                .frame(maxWidth: .infinity, alignment: .trailing)
            Text("\(aScore)–\(bScore)")
                .font(.csMono(14, weight: .heavy))
                .foregroundColor(.csText)
                .monospacedDigit()
                .padding(.horizontal, 6)
            Text(TeamStyle.lookup(teamB, league: league).abbr)
                .font(.system(size: 12, weight: winner == teamB ? .heavy : .semibold))
                .foregroundColor(winner == teamB ? .csText : .csSub)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    var body: some View {
        if let game = toGame() {
            NavigationLink { GameDetailView(game: game) } label: { rowContent }
                .buttonStyle(.plain)
        } else {
            rowContent
        }
    }
}

// MARK: - Home/away split card

private struct HomeAwaySplitCard: View {
    let team: String
    let league: String
    let stats: HomeAwayStats
    let isMLB: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                TeamBadge(team: team, league: league, size: 24)
                Text(TeamStyle.nickname(for: team, league: league))
                    .font(.system(size: 12, weight: .heavy))
                    .kerning(0.4)
                    .foregroundColor(.csText)
                    .lineLimit(1)
            }

            row(label: "HOME", split: stats.home)
            row(label: "AWAY", split: stats.away)

            HStack {
                Text("").frame(width: 38)
                legend(isMLB ? "Avg R" : "Avg Pts")
                legend("Allowed")
                legend("Win%")
            }
            .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    @ViewBuilder
    private func row(label: String, split: LocationStats) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(size: 10, weight: .heavy))
                .kerning(0.6)
                .foregroundColor(.csSub)
                .frame(width: 38, alignment: .leading)
            Text(String(format: "%.1f", split.avg_scored))
                .font(.csMono(12, weight: .bold))
                .foregroundColor(.csText)
                .frame(maxWidth: .infinity)
            Text(String(format: "%.1f", split.avg_conceded))
                .font(.csMono(12, weight: .semibold))
                .foregroundColor(.csSub)
                .frame(maxWidth: .infinity)
            Text(String(format: "%.0f%%", split.win_pct))
                .font(.csMono(12, weight: .bold))
                .foregroundColor(split.win_pct >= 50 ? .csWin : .csLoss)
                .frame(maxWidth: .infinity)
        }
    }

    @ViewBuilder
    private func legend(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9, weight: .heavy))
            .kerning(0.5)
            .foregroundColor(.csFaint)
            .frame(maxWidth: .infinity)
    }
}

private struct FactorBar: View {
    let lean: Double
    let colorA: Color
    let colorB: Color

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let halfW = w / 2
            let fillW = halfW * min(1, abs(lean))
            ZStack(alignment: .center) {
                Capsule().fill(Color.csChip)
                HStack(spacing: 0) {
                    Spacer()
                    if lean < 0 {
                        Capsule().fill(colorB).frame(width: fillW)
                    } else {
                        Color.clear.frame(width: 0)
                    }
                    if lean > 0 {
                        Capsule().fill(colorA).frame(width: fillW)
                    } else {
                        Color.clear.frame(width: 0)
                    }
                    Spacer()
                }
                .frame(width: w)
                Rectangle().fill(Color.csBorder).frame(width: 1, height: 10)
            }
        }
    }
}
