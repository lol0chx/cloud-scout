import SwiftUI

struct FormView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var team = ""
    @State private var form: TeamForm?
    @State private var loading = false
    @State private var error = ""

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

                        teamPicker
                            .padding(.horizontal, 16)

                        if !error.isEmpty {
                            Text(error).foregroundColor(.csLive).padding(.horizontal, 16)
                        } else if loading && form == nil {
                            HStack { Spacer(); ProgressView().tint(.csNBA); Spacer() }
                                .padding(.top, 40)
                        } else if let f = form, !team.isEmpty {
                            hero(form: f)
                                .padding(.horizontal, 14)

                            lastTenSection(f)

                            miniStatsGrid(f)
                                .padding(.horizontal, 14)

                            trendSection(f)

                            gameLogSection(f)
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
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
        .onChange(of: team) { _, _ in Task { await load() } }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("TRENDS")
                .font(.csSection)
                .kerning(1.0)
                .foregroundColor(.csSub)
            Text("Team Form")
                .font(.csEditorial(40))
                .foregroundColor(.csText)
        }
    }

    private var teamPicker: some View {
        HStack(spacing: 8) {
            Image(systemName: "person.2.fill")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.csSub)
            Menu {
                ForEach(teams, id: \.self) { t in
                    Button(t) { team = t }
                }
            } label: {
                HStack {
                    Text(team.isEmpty ? "Select team" : team)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.csText)
                    Spacer()
                    Image(systemName: "chevron.down")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(.csFaint)
                }
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(Color.csBorder, lineWidth: 1))
    }

    // MARK: - Hero

    @ViewBuilder
    private func hero(form f: TeamForm) -> some View {
        let color = TeamStyle.lookup(team, league: state.sport.rawValue).color
        let isMLB = state.sport == .MLB
        let netLabel = isMLB ? "RUN DIFF" : "NET RTG"

        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                TeamBadge(team: team, league: state.sport.rawValue, size: 52)
                VStack(alignment: .leading, spacing: 3) {
                    Text("\(state.sport.rawValue) · \(TeamStyle.lookup(team, league: state.sport.rawValue).abbr)")
                        .font(.csSection)
                        .kerning(0.6)
                        .foregroundColor(.white.opacity(0.75))
                    Text(TeamStyle.nickname(for: team, league: state.sport.rawValue))
                        .font(.csEditorial(30))
                        .foregroundColor(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                Spacer(minLength: 0)
            }

            HStack(spacing: 10) {
                heroStat(v: "\(f.games)G", l: "GAMES")
                heroStat(v: "\(f.streak_type)\(f.streak_count)", l: "STREAK", accent: true)
                heroStat(v: String(format: "%+.1f", f.net_rating), l: netLabel)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(
                colors: [color, color.opacity(0.72)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func heroStat(v: String, l: String, accent: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(v)
                .font(.csMono(22, weight: .heavy))
                .foregroundColor(.white)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(l)
                .font(.csSection)
                .kerning(0.6)
                .foregroundColor(.white.opacity(0.75))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.white.opacity(accent ? 0.15 : 0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    // MARK: - Last 10

    @ViewBuilder
    private func lastTenSection(_ f: TeamForm) -> some View {
        let last10 = Array(f.form_log.sorted { $0.date > $1.date }.prefix(10))
        SectionHeader(title: "Last \(min(10, last10.count))") {
            HStack(spacing: 4) {
                ForEach(Array(last10.enumerated()), id: \.offset) { _, g in
                    Text(g.result)
                        .font(.system(size: 10, weight: .heavy))
                        .foregroundColor(.white)
                        .frame(width: 18, height: 18)
                        .background(g.result == "W" ? Color.csWin : Color.csLoss)
                        .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
                }
            }
        }
        .padding(.horizontal, 16)
    }

    // MARK: - Mini stats grid

    @ViewBuilder
    private func miniStatsGrid(_ f: TeamForm) -> some View {
        let isMLB = state.sport == .MLB
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
            MiniStat(
                label: isMLB ? "Avg Runs" : "Avg Scored",
                value: String(format: "%.1f", f.avg_scored),
                sub: isMLB ? "runs scored / game" : "points / game",
                positive: true
            )
            MiniStat(
                label: isMLB ? "Avg Allowed" : "Avg Conceded",
                value: String(format: "%.1f", f.avg_conceded),
                sub: isMLB ? "runs allowed / game" : "points / game",
                positive: false
            )
            MiniStat(
                label: isMLB ? "Run Diff" : "Net Rating",
                value: String(format: "%+.1f", f.net_rating),
                sub: f.net_rating >= 0 ? "positive" : "negative",
                positive: f.net_rating >= 0
            )
            MiniStat(
                label: "Win Rate",
                value: String(format: "%.0f%%", winRate(f)),
                sub: "last \(f.games) games",
                positive: winRate(f) >= 50
            )
        }
    }

    private func winRate(_ f: TeamForm) -> Double {
        guard f.games > 0 else { return 0 }
        let wins = f.form_log.filter { $0.result == "W" }.count
        return Double(wins) / Double(f.games) * 100
    }

    // MARK: - Trend

    @ViewBuilder
    private func trendSection(_ f: TeamForm) -> some View {
        SectionHeader(title: "Scoring Trend")
            .padding(.horizontal, 16)

        TrendChart(
            points: f.form_log.sorted { $0.date < $1.date }.map { Double($0.scored) },
            headline: String(format: "%.1f", f.avg_scored),
            accent: TeamStyle.lookup(team, league: state.sport.rawValue).color
        )
        .padding(.horizontal, 14)
    }

    // MARK: - Game log

    @ViewBuilder
    private func gameLogSection(_ f: TeamForm) -> some View {
        SectionHeader(title: "Game Log")
            .padding(.horizontal, 16)

        VStack(spacing: 6) {
            ForEach(f.form_log.sorted { $0.date > $1.date }) { g in
                FormGameRow(game: g, league: state.sport.rawValue)
            }
        }
        .padding(.horizontal, 14)
    }

    // MARK: - Data

    private func loadTeams() async {
        form = nil
        do {
            teams = try await API.teams(league: state.sport)
            if let first = teams.first { team = first }
        } catch { teams = [] }
        await load()
    }

    private func load() async {
        guard !team.isEmpty else { return }
        loading = true; error = ""
        do { form = try await API.teamForm(league: state.sport, team: team) }
        catch let e { error = e.localizedDescription; form = nil }
        loading = false
    }
}

// MARK: - MiniStat

private struct MiniStat: View {
    let label: String
    let value: String
    let sub: String
    let positive: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.csSub)
            Text(value)
                .font(.csMono(22, weight: .heavy))
                .foregroundColor(.csText)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(sub)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(positive ? .csWin : .csSub)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - Trend chart

private struct TrendChart: View {
    let points: [Double]
    let headline: String
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(headline)
                    .font(.csMono(24, weight: .heavy))
                    .foregroundColor(.csText)
                    .monospacedDigit()
                Spacer()
                Text("last \(points.count) games")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.csSub)
            }
            SparkLine(points: points, accent: accent)
                .frame(height: 90)
            HStack {
                Text("\(points.count)g ago")
                Spacer()
                Text("now")
            }
            .font(.system(size: 10))
            .foregroundColor(.csFaint)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

private struct SparkLine: View {
    let points: [Double]
    let accent: Color

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let count = points.count
            guard count >= 2 else {
                return AnyView(Color.clear)
            }
            let lo = points.min() ?? 0
            let hi = points.max() ?? 1
            let range = max(hi - lo, 1)
            let padding: CGFloat = 6
            let innerH = h - padding * 2
            let coords: [CGPoint] = points.enumerated().map { i, p in
                let x = CGFloat(i) / CGFloat(count - 1) * w
                let y = h - padding - CGFloat((p - lo) / range) * innerH
                return CGPoint(x: x, y: y)
            }

            let line = Path { path in
                path.move(to: coords[0])
                for c in coords.dropFirst() { path.addLine(to: c) }
            }
            let area = Path { path in
                path.move(to: CGPoint(x: 0, y: h))
                for c in coords { path.addLine(to: c) }
                path.addLine(to: CGPoint(x: w, y: h))
                path.closeSubpath()
            }

            return AnyView(ZStack {
                area.fill(
                    LinearGradient(
                        colors: [accent.opacity(0.25), accent.opacity(0)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                line.stroke(accent, style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
                ForEach(Array(coords.enumerated()), id: \.offset) { i, c in
                    Circle()
                        .fill(accent)
                        .frame(width: i == coords.count - 1 ? 8 : 5, height: i == coords.count - 1 ? 8 : 5)
                        .position(c)
                }
            })
        }
    }
}

// MARK: - Form game row

private struct FormGameRow: View {
    let game: FormGame
    let league: String

    private var won: Bool { game.result == "W" }

    var body: some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 2)
                .fill(won ? Color.csWin : Color.csLoss)
                .frame(width: 3, height: 36)

            VStack(alignment: .leading, spacing: 2) {
                Text("\(game.location == "Home" ? "vs" : "@") \(TeamStyle.nickname(for: game.opponent, league: league))")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.csText)
                    .lineLimit(1)
                Text(formattedDate(game.date))
                    .font(.system(size: 11))
                    .foregroundColor(.csSub)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(game.result)
                .font(.system(size: 13, weight: .heavy))
                .foregroundColor(won ? .csWin : .csLoss)
                .frame(width: 22, alignment: .center)

            Text("\(game.scored)–\(game.conceded)")
                .font(.csMono(13, weight: .bold))
                .foregroundColor(.csText)
                .monospacedDigit()
                .frame(width: 60, alignment: .center)

            Text(String(format: "%.1f", game.rolling_avg))
                .font(.csMono(11, weight: .regular))
                .foregroundColor(.csSub)
                .monospacedDigit()
                .frame(width: 40, alignment: .trailing)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.csCard)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private func formattedDate(_ raw: String) -> String {
        let inFmt = DateFormatter()
        inFmt.dateFormat = "yyyy-MM-dd"
        guard let d = inFmt.date(from: raw) else { return raw }
        let out = DateFormatter()
        out.dateFormat = "MMM d"
        return out.string(from: d)
    }
}
