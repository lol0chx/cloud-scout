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

struct H2HResponse: Codable {
    let games: [[String: AnyCodable]]
    let team_a_wins: Int
    let team_b_wins: Int
    let avg_total: Double
}

struct HomeAwayStats: Codable {
    let home: LocationStats
    let away: LocationStats
}

struct LocationStats: Codable {
    let games: Int
    let avg_scored: Double
    let avg_conceded: Double
    let win_pct: Double
}

struct TopPerformersResponse: Codable {
    let players: [NBATopPlayer]?
    let batters: [MLBBatter]?
    let pitchers: [MLBPitcher]?
}

struct NBATopPlayer: Codable, Identifiable {
    var id: String { player }
    let player: String
    let avg_points: Double
    let avg_assists: Double
    let avg_rebounds: Double
    let games: Int
}

struct MLBBatter: Codable, Identifiable {
    var id: String { player }
    let player: String
    let AVG: Double
    let HR: Int
    let RBI: Int
    let games: Int
}

struct MLBPitcher: Codable, Identifiable {
    var id: String { player }
    let player: String
    let ERA: Double
    let WHIP: Double
    let IP: Double
    let SO: Int
    let games: Int
}

// Simple Codable wrapper for mixed-type JSON values
struct AnyCodable: Codable {
    let value: Any
    init(_ value: Any) { self.value = value }
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let i = try? c.decode(Int.self)    { value = i; return }
        if let d = try? c.decode(Double.self) { value = d; return }
        if let s = try? c.decode(String.self) { value = s; return }
        if let b = try? c.decode(Bool.self)   { value = b; return }
        value = ""
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        if let i = value as? Int    { try c.encode(i) }
        else if let d = value as? Double { try c.encode(d) }
        else if let s = value as? String { try c.encode(s) }
        else if let b = value as? Bool   { try c.encode(b) }
    }
    var stringValue: String { "\(value)" }
}

struct ChatMessage: Identifiable, Codable {
    var id = UUID()
    let role: String   // "user" | "assistant"
    let content: String

    enum CodingKeys: String, CodingKey { case role, content }
}
