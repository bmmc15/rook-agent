import Foundation
import SwiftUI

enum RuntimeState: String {
    case idle
    case listening
    case processing
    case speaking
    case error
    case unknown

    var title: String {
        switch self {
        case .idle:
            return "Pronta"
        case .listening:
            return "A ouvir"
        case .processing:
            return "A pensar"
        case .speaking:
            return "A falar"
        case .error:
            return "Atenção"
        case .unknown:
            return "A iniciar"
        }
    }

    var symbolName: String {
        switch self {
        case .idle:
            return "chess-rook.fill"
        case .listening:
            return "waveform.circle.fill"
        case .processing:
            return "sparkles"
        case .speaking:
            return "speaker.wave.3.fill"
        case .error:
            return "exclamationmark.triangle.fill"
        case .unknown:
            return "circle.dotted"
        }
    }

    var tint: Color {
        switch self {
        case .idle:
            return Color(red: 0.19, green: 0.55, blue: 0.95)
        case .listening:
            return Color(red: 0.12, green: 0.78, blue: 0.57)
        case .processing:
            return Color(red: 0.98, green: 0.63, blue: 0.19)
        case .speaking:
            return Color(red: 0.96, green: 0.39, blue: 0.35)
        case .error:
            return Color(red: 0.85, green: 0.18, blue: 0.22)
        case .unknown:
            return Color.gray
        }
    }
}

enum ConversationMode: String {
    case agent
    case audio

    var title: String {
        switch self {
        case .agent:
            return "Agente"
        case .audio:
            return "Voz Rápida"
        }
    }
}

enum ConnectionState {
    case launching
    case connected
    case disconnected

    var title: String {
        switch self {
        case .launching:
            return "A iniciar"
        case .connected:
            return "Ligado"
        case .disconnected:
            return "Offline"
        }
    }
}

enum TranscriptRole {
    case user
    case assistant
}

struct TranscriptEntry: Identifiable {
    let id = UUID()
    let turnID: UUID
    let role: TranscriptRole
    var text: String
    var pending: Bool
}

@MainActor
final class RookMenuBarModel: ObservableObject {
    @Published var state: RuntimeState = .unknown
    @Published var mode: ConversationMode = .agent
    @Published var openClawConnection: ConnectionState = .launching
    @Published var hint: String = "A iniciar o Rook…"
    @Published var draft: String = ""
    @Published var transcript: [TranscriptEntry] = []
    @Published var audioBars: [Double] = Array(repeating: 0.08, count: 14)
    @Published var speakingLevel: Double = 0.0
    @Published var voiceConfigured = false
    @Published var openClawConfigured = false

    private let bridge = BridgeProcess()
    private var started = false
    private var currentTurnID = UUID()

    init() {
        bridge.onEvent = { [weak self] envelope in
            self?.handle(event: envelope)
        }
        bridge.onTermination = { [weak self] message in
            self?.hint = message
            self?.openClawConnection = .disconnected
        }
    }

    var menuBarSymbol: String {
        state.symbolName
    }

    var isListening: Bool {
        state == .listening
    }

    func startIfNeeded() {
        guard !started else {
            return
        }
        started = true

        do {
            try bridge.start()
            bridge.send(.snapshot)
        } catch {
            hint = "Nao foi possivel arrancar a app."
            openClawConnection = .disconnected
        }
    }

    func sendDraft() {
        let trimmed = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return
        }

        bridge.send(.sendText(trimmed))
        draft = ""
    }

    func setMode(_ mode: ConversationMode) {
        self.mode = mode
        bridge.send(.setMode(mode.rawValue))
    }

    func beginListening() {
        bridge.send(.startListening)
    }

    func endListening() {
        bridge.send(.stopListening)
    }

    func hardStopVoice() {
        bridge.send(.hardStopVoice)
    }

    func stop() {
        bridge.stop()
    }

    private func handle(event: BridgeEnvelope) {
        switch event.type {
        case "ready":
            state = RuntimeState(rawValue: event.state ?? "") ?? .unknown
            mode = ConversationMode(rawValue: event.mode ?? "") ?? .agent
            voiceConfigured = event.voice_configured ?? false
            openClawConfigured = event.openclaw_configured ?? false
            hint = voiceConfigured
                ? "Clica no microfone para falar ou escreve uma mensagem."
                : "A voz precisa de uma chave Gemini configurada."

        case "snapshot":
            state = RuntimeState(rawValue: event.state ?? "") ?? .unknown
            mode = ConversationMode(rawValue: event.mode ?? "") ?? .agent

        case "state":
            state = RuntimeState(rawValue: event.state ?? "") ?? .unknown
            if let status = localizedHint(from: event.status), !status.isEmpty {
                hint = status
            }

        case "hint":
            if let text = localizedHint(from: event.text), !text.isEmpty {
                hint = text
            }

        case "status":
            if let text = localizedHint(from: event.text), !text.isEmpty {
                hint = text
            }

        case "mode":
            mode = ConversationMode(rawValue: event.mode ?? "") ?? mode
            if let message = localizedHint(from: event.message) {
                hint = message
            }

        case "connection":
            if event.target == "openclaw" {
                openClawConnection = event.status == "connected" ? .connected : .disconnected
            }

        case "transcript_clear":
            currentTurnID = UUID()

        case "transcript":
            guard let text = event.text, let roleRaw = event.role else {
                return
            }
            let role: TranscriptRole = roleRaw == "assistant" ? .assistant : .user
            upsertTranscript(role: role, text: text, pending: event.pending ?? false)

        case "audio_level":
            if let bars = event.bars, !bars.isEmpty {
                audioBars = normalizeBars(bars)
            }

        case "speaking_level":
            speakingLevel = event.level ?? 0

        case "command_result":
            if event.ok == false {
                hint = "Essa acao nao esta disponivel neste estado."
            } else if event.command == "hard_stop_voice" {
                hint = "Voz interrompida."
            }

        case "error":
            hint = localizedHint(from: event.message) ?? "Erro interno do backend."
            state = .error

        default:
            break
        }
    }

    private func upsertTranscript(role: TranscriptRole, text: String, pending: Bool) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else {
            return
        }

        if let lastIndex = transcript.lastIndex(where: { $0.turnID == currentTurnID && $0.role == role }) {
            transcript[lastIndex].text = normalized
            transcript[lastIndex].pending = pending
            return
        }

        transcript.append(
            TranscriptEntry(
                turnID: currentTurnID,
                role: role,
                text: normalized,
                pending: pending
            )
        )
    }

    private func normalizeBars(_ values: [Double]) -> [Double] {
        let targetCount = 14
        if values.count == targetCount {
            return values
        }
        if values.count < targetCount {
            return values + Array(repeating: values.last ?? 0.05, count: targetCount - values.count)
        }

        let stride = Double(values.count) / Double(targetCount)
        return (0..<targetCount).map { index in
            let start = Int(Double(index) * stride)
            let end = min(values.count, Int(Double(index + 1) * stride))
            let slice = values[start..<max(start + 1, end)]
            return slice.reduce(0, +) / Double(slice.count)
        }
    }

    private func localizedHint(from raw: String?) -> String? {
        guard let raw else {
            return nil
        }

        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return nil
        }

        switch trimmed {
        case "Press Space to talk...":
            return "Clica no microfone para falar."
        case "Listening...":
            return "A ouvir..."
        case "Speaking...":
            return "A falar..."
        case "Starting services in background. You can type commands now.":
            return "A ligar os servicos. Ja podes escrever ou usar o microfone."
        case "Press Space to talk, or type text. Default mode: /agent":
            return "Clica no microfone para falar ou escreve. Modo atual: Agente."
        case "Some voice services are still unavailable. Text commands are ready.":
            return "Alguns servicos de voz ainda nao estao prontos. O texto ja funciona."
        case "Audio mode enabled. New turns go straight to Gemini voice.":
            return "Modo Voz Rapida ativo. Os novos pedidos vao diretos para a voz."
        case "Agent mode enabled. New turns go through OpenClaw.":
            return "Modo Agente ativo. Os novos pedidos passam pelo OpenClaw."
        default:
            return trimmed
        }
    }
}
