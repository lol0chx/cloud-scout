import Foundation

enum Sport: String, CaseIterable, Identifiable {
    case NBA, MLB
    var id: String { rawValue }
}

struct Game: Codable, Identifiable {
    let id: Int
    let date: String
    let home_team: String
    let away_team: String
    let home_score: Int
    let away_score: Int
    let league: String
    let season: String
}

struct Standing: Codable, Identifiable {
    var id: String { Team }
    let Team: String
    let W: Int
    let L: Int
    let GP: Int
    let winPct: Double
    let avgPts: Double
    let avgAllowed: Double
    let netRtg: Double
    let Streak: String

    enum CodingKeys: String, CodingKey {
        case Team, W, L, GP, Streak
        case winPct     = "Win%"
        case avgPts     = "Avg Pts"
        case avgAllowed = "Avg Allowed"
        case netRtg     = "Net Rtg"
    }
}

struct TeamForm: Codable {
    let team: String
    let games: Int
    let streak_count: Int
    let streak_type: String
    let avg_scored: Double
    let avg_conceded: Double
    let net_rating: Double
    let form_log: [FormGame]
}

struct FormGame: Codable, Identifiable {
    var id: String { date + opponent }
    let date: String
    let location: String
    let opponent: String
    let result: String
    let scored: Int
    let conceded: Int
    let margin: Int
    let rolling_avg: Double
}

struct Prediction: Codable {
    let team_a: String
    let team_b: String
    let prob_a: Double
    let prob_b: Double
    let margin: Double
    let team_a_record: TeamRecord
    let team_b_record: TeamRecord
    let team_a_streak: TeamStreak
    let team_b_streak: TeamStreak
}

struct TeamRecord: Codable {
    let wins: Int
    let losses: Int
    let win_pct: Double
}

struct TeamStreak: Codable {
    let count: Int
    let type: String
}

struct ChatMessage: Identifiable, Codable {
    var id = UUID()
    let role: String   // "user" | "assistant"
    let content: String

    enum CodingKeys: String, CodingKey { case role, content }
}
