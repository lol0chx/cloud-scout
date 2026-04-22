import SwiftUI

@MainActor
class AppState: ObservableObject {
    @Published var sport: Sport = .NBA
    @Published var selectedTab: Int = 0
    @Published var pendingPredictMatchup: PredictMatchup?
}

struct PredictMatchup: Equatable {
    let sport: Sport
    let homeTeam: String
    let awayTeam: String
}
