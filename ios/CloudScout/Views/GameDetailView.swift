import SwiftUI

struct GameDetailView: View {
    let game: Game
    var selectedTeam: String = ""

    private var homeWon: Bool { game.home_score > game.away_score }
    private var isTeamHome: Bool { game.home_team == selectedTeam }
    private var teamWon: Bool { isTeamHome ? homeWon : !homeWon }
    private var hasTeam: Bool { !selectedTeam.isEmpty && (game.home_team == selectedTeam || game.away_team == selectedTeam) }

    var body: some View {
        ZStack {
            Color.appBg.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 16) {
                    // Score card
                    VStack(spacing: 20) {
                        Text(game.date)
                            .font(.system(size: 13)).foregroundColor(.appSub)

                        HStack(alignment: .center, spacing: 0) {
                            // Home team
                            VStack(spacing: 8) {
                                Text(game.home_team)
                                    .font(.system(size: 15, weight: .semibold))
                                    .foregroundColor(homeWon ? .white : .appSub)
                                    .multilineTextAlignment(.center)
                                    .lineLimit(2)
                                Text("\(game.home_score)")
                                    .font(.system(size: 48, weight: .heavy))
                                    .foregroundColor(homeWon ? .white : .appSub)
                                Text("HOME")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundColor(.appSub).kerning(0.8)
                            }
                            .frame(maxWidth: .infinity)

                            VStack(spacing: 4) {
                                Text("FINAL").font(.system(size: 11, weight: .semibold)).foregroundColor(.appSub).kerning(0.8)
                                Text("–").font(.system(size: 28, weight: .bold)).foregroundColor(.appBorder)
                            }
                            .frame(width: 50)

                            // Away team
                            VStack(spacing: 8) {
                                Text(game.away_team)
                                    .font(.system(size: 15, weight: .semibold))
                                    .foregroundColor(!homeWon ? .white : .appSub)
                                    .multilineTextAlignment(.center)
                                    .lineLimit(2)
                                Text("\(game.away_score)")
                                    .font(.system(size: 48, weight: .heavy))
                                    .foregroundColor(!homeWon ? .white : .appSub)
                                Text("AWAY")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundColor(.appSub).kerning(0.8)
                            }
                            .frame(maxWidth: .infinity)
                        }

                        if hasTeam {
                            Text(teamWon ? "WIN" : "LOSS")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(teamWon ? .appWin : .appLoss)
                                .padding(.horizontal, 16).padding(.vertical, 6)
                                .background((teamWon ? Color.appWin : Color.appLoss).opacity(0.15))
                                .clipShape(Capsule())
                        }
                    }
                    .padding(24)
                    .background(Color.appCard)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .padding(.horizontal, 16)

                    // Details
                    VStack(spacing: 0) {
                        DetailRow(label: "League", value: game.league)
                        Divider().background(Color.appBorder)
                        DetailRow(label: "Season", value: game.season)
                        Divider().background(Color.appBorder)
                        DetailRow(label: "Margin", value: "\(abs(game.home_score - game.away_score)) \(game.league == "MLB" ? "runs" : "pts")")
                        Divider().background(Color.appBorder)
                        DetailRow(label: "Total", value: "\(game.home_score + game.away_score) \(game.league == "MLB" ? "runs" : "pts")")
                        if hasTeam {
                            Divider().background(Color.appBorder)
                            DetailRow(label: "Location", value: isTeamHome ? "Home" : "Away")
                        }
                    }
                    .background(Color.appCard)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal, 16)
                }
                .padding(.top, 16).padding(.bottom, 40)
            }
        }
        .navigationTitle("\(game.home_team) vs \(game.away_team)")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct DetailRow: View {
    let label: String; let value: String
    var body: some View {
        HStack {
            Text(label).font(.system(size: 14)).foregroundColor(.appSub)
            Spacer()
            Text(value).font(.system(size: 14, weight: .semibold)).foregroundColor(.white)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
    }
}
