import SwiftUI

@MainActor
class AppState: ObservableObject {
    @Published var sport: Sport = .NBA
}
