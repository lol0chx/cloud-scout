import SwiftUI

// MARK: - Team identity (abbreviation + brand color + nickname)

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
            color: league.uppercased() == "MLB" ? .csMLB : .csNBA
        )
    }

    static func nickname(for team: String, league: String) -> String {
        let key = team.lowercased().trimmingCharacters(in: .whitespaces)
        if league.uppercased() == "MLB", let n = mlbNicknames[key] { return n }
        if league.uppercased() == "NBA", let n = nbaNicknames[key] { return n }
        return team.split(separator: " ").last.map(String.init) ?? team
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

// MARK: - TeamBadge — circle with 3-letter abbreviation on team color

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

// MARK: - LeagueTile — rounded-square NBA / MLB tile

struct LeagueTile: View {
    let league: String      // "NBA" / "MLB"
    var size: CGFloat = 36

    private var color: Color {
        league.uppercased() == "MLB" ? .csMLB : .csNBA
    }

    var body: some View {
        Text(league.uppercased())
            .font(.system(size: size * 0.30, weight: .heavy, design: .rounded))
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(
                RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
                    .fill(color)
            )
    }
}

// MARK: - SourceHeader — feed-card header row

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
                    .foregroundColor(.csText)
                Text(timestamp)
                    .font(.system(size: 12))
                    .foregroundColor(.csSub)
            }
            Spacer()
            if showsMenu {
                Image(systemName: "ellipsis")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.csSub)
                    .frame(width: 28, height: 28)
            }
        }
    }
}

// MARK: - Chip — pill with optional icon (chip bg, 10pt radius)

struct Chip: View {
    let icon: String?
    let text: String
    var background: Color = .csChip
    var foreground: Color = .csSub
    var fontSize: CGFloat = 13
    var weight: Font.Weight = .semibold

    init(
        icon: String? = nil,
        text: String,
        background: Color = .csChip,
        foreground: Color = .csSub,
        fontSize: CGFloat = 13,
        weight: Font.Weight = .semibold
    ) {
        self.icon = icon
        self.text = text
        self.background = background
        self.foreground = foreground
        self.fontSize = fontSize
        self.weight = weight
    }

    var body: some View {
        HStack(spacing: 6) {
            if let icon {
                Image(systemName: icon).font(.system(size: fontSize - 1, weight: weight))
            }
            Text(text).font(.system(size: fontSize, weight: weight))
        }
        .foregroundColor(foreground)
        .padding(.horizontal, 12).padding(.vertical, 7)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

// MARK: - StatusPill — live / final / scheduled / injury

struct StatusPill: View {
    enum Kind {
        case live, final, scheduled, out, doubtful, questionable

        var palette: StatusPillPalette {
            switch self {
            case .live:          return .live
            case .final:         return .final
            case .scheduled:     return .scheduled
            case .out:           return .out
            case .doubtful:      return .doubtful
            case .questionable:  return .questionable
            }
        }

        var showsDot: Bool { self == .live }
    }

    let kind: Kind
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            if kind.showsDot {
                Circle()
                    .fill(kind.palette.foreground)
                    .frame(width: 6, height: 6)
            }
            Text(text.uppercased())
                .font(.system(size: 10, weight: .heavy))
                .kerning(0.6)
        }
        .foregroundColor(kind.palette.foreground)
        .padding(.horizontal, 9).padding(.vertical, 4)
        .background(kind.palette.background)
        .clipShape(Capsule())
    }
}

// MARK: - SectionHeader — uppercase tracked header with optional trailing action

struct SectionHeader<Trailing: View>: View {
    let title: String
    @ViewBuilder let trailing: () -> Trailing

    var body: some View {
        HStack(alignment: .center) {
            Text(title.uppercased())
                .font(.csSection)
                .kerning(1.0)
                .foregroundColor(.csSub)
            Spacer()
            trailing()
        }
    }
}

extension SectionHeader where Trailing == EmptyView {
    init(title: String) {
        self.init(title: title, trailing: { EmptyView() })
    }
}

// MARK: - StatBox — chip-bg stat tile (value + small label)

struct StatBox: View {
    let value: String
    let label: String
    var accent: Color = .csText
    var background: Color = .csChip

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.csMono(17, weight: .bold))
                .foregroundColor(accent)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text(label.uppercased())
                .font(.system(size: 10, weight: .bold))
                .kerning(0.6)
                .foregroundColor(.csSub)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

// MARK: - SportToggle — NBA/MLB segmented control (light surface)

struct SportToggle: View {
    @Binding var sport: Sport

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Sport.allCases) { s in
                Button {
                    sport = s
                } label: {
                    Text(s.rawValue)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(sport == s ? .white : .csSub)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(
                            sport == s
                                ? (s == .NBA ? Color.csNBA : Color.csMLB)
                                : Color.clear
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Color.csChip)
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

// MARK: - Card surface modifier

struct CSCard: ViewModifier {
    var radius: CGFloat = 14
    var padding: EdgeInsets = EdgeInsets(top: 16, leading: 18, bottom: 16, trailing: 18)
    var background: Color = .csCard

    func body(content: Content) -> some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(padding)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
}

extension View {
    func csCard(radius: CGFloat = 14, padding: EdgeInsets = EdgeInsets(top: 16, leading: 18, bottom: 16, trailing: 18), background: Color = .csCard) -> some View {
        modifier(CSCard(radius: radius, padding: padding, background: background))
    }
}
