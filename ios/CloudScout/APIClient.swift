import Foundation

// Change to your local IP when testing on a physical device
// e.g. "http://192.168.1.100:8000"
let API_BASE = ProcessInfo.processInfo.environment["API_BASE"] ?? "http://10.192.233.52:8000"

struct ChatPayload: Encodable {
    let league: String
    let message: String
    let history: [ChatHistoryItem]
}
struct ChatHistoryItem: Encodable {
    let role: String
    let content: String
}
struct ChatResponse: Decodable {
    let response: String
}

enum APIError: LocalizedError {
    case badStatus(Int)
    case message(String)
    var errorDescription: String? {
        switch self {
        case .badStatus(let c): return "Server error \(c)"
        case .message(let m):   return m
        }
    }
}

struct API {
    private static func get<T: Decodable>(_ path: String) async throws -> T {
        let url = URL(string: API_BASE + path)!
        let (data, res) = try await URLSession.shared.data(from: url)
        if let http = res as? HTTPURLResponse, http.statusCode != 200 {
            throw APIError.badStatus(http.statusCode)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private static func post<T: Decodable>(_ path: String, body: Encodable) async throws -> T {
        let url = URL(string: API_BASE + path)!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(body)
        let (data, res) = try await URLSession.shared.data(for: req)
        if let http = res as? HTTPURLResponse, http.statusCode != 200 {
            throw APIError.badStatus(http.statusCode)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private static func enc(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s
    }

    static func teams(league: Sport) async throws -> [String] {
        try await get("/teams?league=\(league.rawValue)")
    }

    static func games(league: Sport, team: String = "", limit: Int = 30) async throws -> [Game] {
        try await get("/games?league=\(league.rawValue)&team=\(enc(team))&limit=\(limit)")
    }

    static func standings(league: Sport) async throws -> [Standing] {
        try await get("/standings?league=\(league.rawValue)")
    }

    static func teamForm(league: Sport, team: String, n: Int = 15) async throws -> TeamForm {
        try await get("/team/form?league=\(league.rawValue)&team=\(enc(team))&n=\(n)")
    }

    static func prediction(league: Sport, teamA: String, teamB: String) async throws -> Prediction {
        try await get("/team/prediction?league=\(league.rawValue)&team_a=\(enc(teamA))&team_b=\(enc(teamB))")
    }

    static func players(league: Sport, name: String = "", role: String = "") async throws -> [String] {
        try await get("/players?league=\(league.rawValue)&name=\(enc(name))&role=\(enc(role))")
    }

    /// Returns key-value pairs suitable for display
    static func playerStats(league: Sport, name: String, n: Int = 15, role: String = "batter") async throws -> [(String, String)] {
        let url = URL(string: API_BASE + "/player/stats?league=\(league.rawValue)&name=\(enc(name))&n=\(n)&role=\(enc(role))")!
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        let skip = Set(["player", "games", "opponent"])
        return dict
            .filter { !skip.contains($0.key) }
            .sorted { $0.key < $1.key }
            .map { ($0.key, "\($0.value)") }
    }

    static func playerLog(league: Sport, name: String, n: Int = 20, role: String = "batter") async throws -> [[String: String]] {
        let url = URL(string: API_BASE + "/player/log?league=\(league.rawValue)&name=\(enc(name))&n=\(n)&role=\(enc(role))")!
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let arr = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { return [] }
        return arr.map { row in row.mapValues { "\($0)" } }
    }

    static func h2h(league: Sport, teamA: String, teamB: String, n: Int = 10) async throws -> H2HResponse {
        try await get("/team/h2h?league=\(league.rawValue)&team_a=\(enc(teamA))&team_b=\(enc(teamB))&n=\(n)")
    }

    static func homeAway(league: Sport, team: String) async throws -> HomeAwayStats {
        try await get("/team/home-away?league=\(league.rawValue)&team=\(enc(team))")
    }

    static func advancedH2H(teamA: String, teamB: String, n: Int = 10) async throws -> H2HAdvancedResponse {
        try await get("/team/advanced/h2h?team_a=\(enc(teamA))&team_b=\(enc(teamB))&n=\(n)")
    }

    static func projectedTotal(teamA: String, teamB: String, home: String = "", n: Int = 10) async throws -> ProjectedTotalResponse {
        try await get("/predict/total?team_a=\(enc(teamA))&team_b=\(enc(teamB))&home=\(enc(home))&n=\(n)")
    }

    static func topPerformers(league: Sport, team: String = "", n: Int = 15) async throws -> TopPerformersResponse {
        try await get("/team/top-performers?league=\(league.rawValue)&team=\(enc(team))&n=\(n)")
    }

    static func playerVsTeam(league: Sport, name: String, opponent: String, n: Int = 15, role: String = "batter") async throws -> [(String, String)] {
        let url = URL(string: API_BASE + "/player/vs-team?league=\(league.rawValue)&name=\(enc(name))&opponent=\(enc(opponent))&n=\(n)&role=\(enc(role))")!
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        let skip = Set(["player", "games", "opponent"])
        return dict.filter { !skip.contains($0.key) }.sorted { $0.key < $1.key }.map { ($0.key, "\($0.value)") }
    }

    struct ScrapeRequest: Encodable {
        let league: String
        let team: String
        let last: Int
        let season: Int
    }
    struct ScrapeResponse: Decodable {
        let games_added: Int
        let players_added: Int
    }

    // ── Injuries ─────────────────────────────────────────────────────────

    static func injuries(league: Sport, team: String = "") async throws -> [Injury] {
        try await get("/injuries?league=\(league.rawValue)&team=\(enc(team))")
    }

    static func refreshInjuries(league: Sport) async throws -> RefreshResponse {
        try await post("/injuries/refresh?league=\(league.rawValue)", body: ["league": league.rawValue])
    }

    // ── Today's Games & Starters ────────────────────────────────────────

    static func todaysGames() async throws -> [TodayGame] {
        try await get("/games/today")
    }

    static func starters(gameId: String) async throws -> StartersResponse {
        try await get("/games/starters/\(gameId)")
    }

    // ── Scrape ──────────────────────────────────────────────────────────

    static func scrapeTeam(league: Sport, team: String, last: Int = 15, season: Int = 2025) async throws -> ScrapeResponse {
        let req = ScrapeRequest(league: league.rawValue, team: team, last: last, season: season)
        return try await post("/scrape/team", body: req)
    }

    static func aiChat(league: Sport, message: String, history: [ChatMessage]) async throws -> String {
        let payload = ChatPayload(
            league: league.rawValue,
            message: message,
            history: history.suffix(10).map { ChatHistoryItem(role: $0.role, content: $0.content) }
        )
        let res: ChatResponse = try await post("/ai/chat", body: payload)
        return res.response
    }
}
