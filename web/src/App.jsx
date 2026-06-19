import { useState } from 'react'
import { MessageSquare, Users, Network, Brain, Wrench, Settings as SettingsIcon } from 'lucide-react'
import ChatTab from './components/ChatTab'
import CouncilTab from './components/CouncilTab'
import GraphTab from './components/GraphTab'
import MemoryTab from './components/MemoryTab'
import ToolsTab from './components/ToolsTab'
import SettingsTab from './components/SettingsTab'

const TABS = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'council', label: 'Council', icon: Users },
  { id: 'graph', label: 'Connections', icon: Network },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export default function App() {
  const [tab, setTab] = useState('chat')
  const [model, setModel] = useState('auto')

  return (
    <div className="h-screen flex bg-slate-950 text-slate-200">
      <nav className="w-44 border-r border-slate-800 p-3 space-y-1">
        <div className="text-cyan-400 font-semibold px-2 pb-3">JARVIS</div>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
              tab === id ? 'bg-cyan-600/20 text-cyan-300' : 'hover:bg-slate-800'}`}>
            <Icon size={16} /> {label}
          </button>
        ))}
      </nav>
      <main className="flex-1 min-w-0">
        {tab === 'chat' && <ChatTab model={model} />}
        {tab === 'council' && <CouncilTab />}
        {tab === 'graph' && <GraphTab />}
        {tab === 'memory' && <MemoryTab />}
        {tab === 'tools' && <ToolsTab />}
        {tab === 'settings' && <SettingsTab model={model} setModel={setModel} />}
      </main>
    </div>
  )
}
