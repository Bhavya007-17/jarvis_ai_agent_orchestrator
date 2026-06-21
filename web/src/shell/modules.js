import { MessageSquare, Mic, Share2, Users, Network, Brain, Wrench, Settings as SettingsIcon } from 'lucide-react'
import ChatTab from '../components/ChatTab'
import VoiceTab from '../components/VoiceTab'
import AgentsTab from '../components/AgentsTab'
import CouncilTab from '../components/CouncilTab'
import GraphTab from '../components/GraphTab'
import MemoryTab from '../components/MemoryTab'
import ToolsTab from '../components/ToolsTab'
import SettingsTab from '../components/SettingsTab'

// One source of truth mapping module id -> bottom-bar entry + window content.
// `props` lists which shell-level props (model/setModel) to forward. ids MUST
// match UI_MODULES in scripts/jarvis_web_api.py.
export const MODULES = [
  { id: 'chat',     label: 'Chat',        icon: MessageSquare, Component: ChatTab,     props: ['model'],            defaultRect: { x: 360, y: 160, w: 560, h: 460 } },
  { id: 'voice',    label: 'Voice',       icon: Mic,           Component: VoiceTab,    props: ['model'],            defaultRect: { x: 400, y: 200, w: 520, h: 440 } },
  { id: 'agents',   label: 'Agents',      icon: Share2,        Component: AgentsTab,   props: [],                   defaultRect: { x: 240, y: 120, w: 900, h: 600 } },
  { id: 'council',  label: 'Council',     icon: Users,         Component: CouncilTab,  props: [],                   defaultRect: { x: 300, y: 150, w: 820, h: 560 } },
  { id: 'graph',    label: 'Connections', icon: Network,       Component: GraphTab,    props: [],                   defaultRect: { x: 260, y: 130, w: 880, h: 600 } },
  { id: 'memory',   label: 'Memory',      icon: Brain,         Component: MemoryTab,   props: [],                   defaultRect: { x: 380, y: 170, w: 560, h: 500 } },
  { id: 'tools',    label: 'Tools',       icon: Wrench,        Component: ToolsTab,    props: [],                   defaultRect: { x: 380, y: 170, w: 600, h: 500 } },
  { id: 'settings', label: 'Settings',    icon: SettingsIcon,  Component: SettingsTab, props: ['model', 'setModel'], defaultRect: { x: 400, y: 180, w: 600, h: 560 } },
]

export const MODULE_BY_ID = Object.fromEntries(MODULES.map((m) => [m.id, m]))
