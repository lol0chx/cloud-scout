import SwiftUI

struct UpdateView: View {
    @EnvironmentObject var state: AppState
    @State private var teams: [String] = []
    @State private var selectedTeam = ""
    @State private var gamesCount = 15
    @State private var scraping = false
    @State private var scrapingAll = false
    @State private var results: [ScrapeResult] = []
    @State private var error = ""

    struct ScrapeResult: Identifiable {
        let id = UUID()
        let team: String
        let gamesAdded: Int
        let playersAdded: Int
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Update Data")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.bottom, 12)
                    SportPicker(sport: $state.sport)

                    // Games to fetch slider
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Games to fetch: \(gamesCount)")
                            .font(.system(size: 13))
                            .foregroundColor(.appSub)
                        Slider(value: Binding(
                            get: { Double(gamesCount) },
                            set: { gamesCount = Int($0) }
                        ), in: 5...50, step: 5)
                        .tint(.appPrimary)
                    }
                    .padding(.bottom, 16)

                    // Single team scrape
                    VStack(alignment: .leading, spacing: 8) {
                        Text("SCRAPE ONE TEAM")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.appSub)
                            .kerning(0.8)

                        Picker("Team", selection: $selectedTeam) {
                            ForEach(teams, id: \.self) { Text($0).tag($0) }
                        }
                        .pickerStyle(.menu)
                        .tint(.appSub)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                        .background(Color.appCard)
                        .clipShape(RoundedRectangle(cornerRadius: 8))

                        Button {
                            Task { await scrapeOne() }
                        } label: {
                            HStack {
                                if scraping {
                                    ProgressView().tint(.white).scaleEffect(0.8)
                                    Text("Scraping...").foregroundColor(.white)
                                } else {
                                    Image(systemName: "arrow.down.circle.fill")
                                    Text("Scrape \(selectedTeam)")
                                }
                            }
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(scraping ? Color.appBorder : Color.appPrimary)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                        .disabled(scraping || scrapingAll || selectedTeam.isEmpty)
                    }
                    .padding(.bottom, 20)

                    // Scrape all teams
                    VStack(alignment: .leading, spacing: 8) {
                        Text("SCRAPE ALL TEAMS")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.appSub)
                            .kerning(0.8)

                        Button {
                            Task { await scrapeAll() }
                        } label: {
                            HStack {
                                if scrapingAll {
                                    ProgressView().tint(.white).scaleEffect(0.8)
                                    Text("Scraping all \(state.sport.rawValue) teams...")
                                        .foregroundColor(.white)
                                } else {
                                    Image(systemName: "arrow.down.circle")
                                    Text("Scrape All \(state.sport.rawValue) Teams")
                                }
                            }
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(scrapingAll ? Color.appBorder : Color(hex: "2a2a3e"))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.appBorder))
                        }
                        .disabled(scraping || scrapingAll)
                    }
                    .padding(.bottom, 20)

                    if !error.isEmpty {
                        Text(error)
                            .foregroundColor(.appLoss)
                            .font(.system(size: 13))
                            .padding(.bottom, 12)
                    }

                    // Results
                    if !results.isEmpty {
                        Text("RESULTS")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.appSub)
                            .kerning(0.8)
                            .padding(.bottom, 8)

                        ForEach(results) { r in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(r.team)
                                        .font(.system(size: 14, weight: .semibold))
                                        .foregroundColor(.white)
                                    Text("\(r.gamesAdded) games · \(r.playersAdded) players added")
                                        .font(.system(size: 12))
                                        .foregroundColor(.appSub)
                                }
                                Spacer()
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(.appWin)
                            }
                            .padding(12)
                            .background(Color.appCard)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .padding(.bottom, 6)
                        }
                    }
                }
                .padding(16)
                .padding(.bottom, 40)
            }
            .background(Color.appBg.ignoresSafeArea())
        }
        .task { await loadTeams() }
        .onChange(of: state.sport) { _, _ in Task { await loadTeams() } }
    }

    private func loadTeams() async {
        results = []
        do {
            teams = try await API.teams(league: state.sport)
            if let first = teams.first { selectedTeam = first }
        } catch { teams = [] }
    }

    private func scrapeOne() async {
        guard !selectedTeam.isEmpty else { return }
        scraping = true; error = ""
        do {
            let res = try await API.scrapeTeam(league: state.sport, team: selectedTeam, last: gamesCount)
            results.insert(ScrapeResult(team: selectedTeam, gamesAdded: res.games_added, playersAdded: res.players_added), at: 0)
        } catch let e {
            error = e.localizedDescription
        }
        scraping = false
    }

    private func scrapeAll() async {
        guard !teams.isEmpty else { return }
        scrapingAll = true; error = ""; results = []
        for team in teams {
            do {
                let res = try await API.scrapeTeam(league: state.sport, team: team, last: gamesCount)
                results.append(ScrapeResult(team: team, gamesAdded: res.games_added, playersAdded: res.players_added))
            } catch {
                // skip failed teams
            }
        }
        scrapingAll = false
    }
}
