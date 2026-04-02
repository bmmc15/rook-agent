import SwiftUI

struct RookPanelView: View {
    @ObservedObject var model: RookMenuBarModel
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 18) {
            header
            StateOrbView(
                state: model.state,
                audioBars: model.audioBars,
                speakingLevel: model.speakingLevel
            )
            .frame(height: 210)

            modePicker
            transcriptSection
            composer
        }
        .padding(18)
        .frame(width: 430, height: 620)
        .background(backgroundGradient)
        .task {
            model.startIfNeeded()
        }
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Label(model.state.title, systemImage: model.state.symbolName)
                    .font(.system(size: 18, weight: .semibold, design: .rounded))
                    .foregroundStyle(model.state.tint)

                Text(model.hint)
                    .font(.system(size: 12, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 8) {
                ConnectionBadge(
                    title: "OpenClaw",
                    state: model.openClawConnection
                )
                if !model.voiceConfigured {
                    Text("Voz indisponivel")
                        .font(.system(size: 11, weight: .semibold, design: .rounded))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color.white.opacity(0.08), in: Capsule())
                }
            }
        }
    }

    private var modePicker: some View {
        HStack(spacing: 10) {
            modeButton(.agent)
            modeButton(.audio)
            stopVoiceButton
            Spacer()
            HoldToTalkMicButton(
                isListening: model.isListening,
                onPressBegan: model.beginListening,
                onPressEnded: model.endListening
            )
        }
    }

    private func modeButton(_ value: ConversationMode) -> some View {
        Button {
            model.setMode(value)
        } label: {
            Text(value.title)
                .font(.system(size: 12, weight: .semibold, design: .rounded))
                .foregroundStyle(model.mode == value ? Color.black : Color.white.opacity(0.82))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    Capsule()
                        .fill(model.mode == value ? Color.white : Color.white.opacity(0.08))
                )
        }
        .buttonStyle(.plain)
    }

    private var stopVoiceButton: some View {
        Button {
            model.hardStopVoice()
        } label: {
            Label("Stop", systemImage: "stop.fill")
                .font(.system(size: 12, weight: .semibold, design: .rounded))
                .foregroundStyle(Color.white.opacity(0.92))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    Capsule()
                        .fill(Color.red.opacity(0.28))
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Parar voz do agente")
    }

    private var transcriptSection: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(model.transcript) { entry in
                    TranscriptBubble(entry: entry)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 4)
        }
        .scrollIndicators(.hidden)
        .padding(14)
        .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Escreve para o Rook…", text: $model.draft, axis: .vertical)
                .textFieldStyle(.plain)
                .focused($inputFocused)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(.white)
                .lineLimit(1...4)
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
                .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .onSubmit {
                    model.sendDraft()
                }

            Button {
                model.sendDraft()
                inputFocused = true
            } label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .black))
                    .foregroundStyle(Color.black)
                    .frame(width: 48, height: 48)
                    .background(Color.white, in: Circle())
            }
            .buttonStyle(.plain)
        }
    }

    private var backgroundGradient: some View {
        LinearGradient(
            colors: [
                Color(red: 0.07, green: 0.10, blue: 0.19),
                Color(red: 0.09, green: 0.16, blue: 0.25),
                Color(red: 0.14, green: 0.10, blue: 0.21),
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(
            Circle()
                .fill(Color.white.opacity(0.08))
                .blur(radius: 70)
                .offset(x: -110, y: -180)
        )
        .overlay(
            Circle()
                .fill(Color.cyan.opacity(0.18))
                .blur(radius: 90)
                .offset(x: 120, y: -110)
        )
    }
}

struct ConnectionBadge: View {
    let title: String
    let state: ConnectionState

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text("\(title) \(state.title)")
                .font(.system(size: 11, weight: .semibold, design: .rounded))
        }
        .foregroundStyle(.white.opacity(0.88))
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color.white.opacity(0.08), in: Capsule())
    }

    private var color: Color {
        switch state {
        case .launching:
            return .orange
        case .connected:
            return .green
        case .disconnected:
            return .red
        }
    }
}

struct TranscriptBubble: View {
    let entry: TranscriptEntry

    var body: some View {
        VStack(alignment: entry.role == .user ? .trailing : .leading, spacing: 5) {
            Text(entry.role == .user ? "Tu" : "Rook")
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .foregroundStyle(.white.opacity(0.62))

            Text(entry.text)
                .font(.system(size: 13, weight: .medium, design: .rounded))
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .background(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(entry.role == .user ? Color.white.opacity(0.16) : Color.white.opacity(0.08))
                )
                .overlay(alignment: .bottomTrailing) {
                    if entry.pending {
                        Text("ao vivo")
                            .font(.system(size: 10, weight: .black, design: .rounded))
                            .foregroundStyle(.white.opacity(0.8))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                    }
                }
        }
        .frame(maxWidth: .infinity, alignment: entry.role == .user ? .trailing : .leading)
    }
}

struct HoldToTalkMicButton: View {
    let isListening: Bool
    let onPressBegan: () -> Void
    let onPressEnded: () -> Void

    @State private var isPressed = false
    @State private var didStartListening = false

    var body: some View {
        ZStack {
            Circle()
                .fill(isListening ? Color.green : Color.white.opacity(0.1))
                .frame(width: 54, height: 54)
                .overlay(
                    Circle()
                        .stroke(Color.white.opacity(0.18), lineWidth: 1)
                )

            Image(systemName: isListening ? "waveform.circle.fill" : "mic.fill")
                .font(.system(size: 20, weight: .black))
                .foregroundStyle(isListening ? Color.black : Color.white)
        }
        .scaleEffect(isPressed || isListening ? 1.04 : 1.0)
        .animation(.spring(response: 0.22, dampingFraction: 0.7), value: isPressed || isListening)
        .contentShape(Circle())
        .onLongPressGesture(minimumDuration: 60, maximumDistance: 24, pressing: handlePressStateChanged) {}
        .accessibilityLabel(isListening ? "Larga para enviar" : "Carrega e segura para falar")
    }

    private func handlePressStateChanged(_ pressing: Bool) {
        if pressing {
            guard !didStartListening else {
                return
            }
            isPressed = true
            didStartListening = true
            onPressBegan()
            return
        }

        let shouldStop = didStartListening
        isPressed = false
        didStartListening = false
        if shouldStop {
            onPressEnded()
        }
    }
}
