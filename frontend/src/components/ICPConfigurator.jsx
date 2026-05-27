import React, { useState } from 'react'
import { Search, Plus, X, Rocket, Sparkles } from 'lucide-react'
import axios from 'axios'

const ICPConfigurator = () => {
  const [keywords, setKeywords] = useState(['CRM for startups', 'real estate recommendations', 'looking for a lawyer'])
  const [inputValue, setInputValue] = useState('')
  const [isScanning, setIsScanning] = useState(false)

  const addKeyword = (e) => {
    e.preventDefault()
    if (inputValue && !keywords.includes(inputValue)) {
      setKeywords([...keywords, inputValue])
      setInputValue('')
    }
  }

  const removeKeyword = (kw) => {
    setKeywords(keywords.filter(k => k !== kw))
  }

  const startScan = async () => {
    if (keywords.length === 0) return
    setIsScanning(true)
    try {
      await axios.post('http://localhost:8000/api/leads/scan', keywords)
      alert(`Scanning Reddit for ${keywords.length} signals...`)
    } catch (err) {
      console.error(err)
      alert("Backend connection failed")
    } finally {
      setIsScanning(false)
    }
  }

  return (
    <div className="bg-white p-8 rounded-3xl border border-gray-100 shadow-sm space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="text-blue-500" size={24} />
          <h2 className="text-xl font-bold text-gray-900">Target ICP Keywords</h2>
        </div>
        <button 
          onClick={startScan}
          disabled={isScanning}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center space-x-2 hover:bg-blue-700 transition-all disabled:bg-blue-300 active:scale-95"
        >
          <Rocket size={18} />
          <span>{isScanning ? 'Scanning...' : 'Start Global Scan'}</span>
        </button>
      </div>

      <p className="text-gray-500 text-sm">
        SocialPipe will monitor these keywords across Reddit to find high-intent conversations and buying signals.
      </p>

      <form onSubmit={addKeyword} className="flex space-x-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Add new signal (e.g. 'best e-commerce platform')"
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
          />
        </div>
        <button type="submit" className="bg-gray-900 text-white p-2.5 rounded-xl hover:bg-black transition-colors">
          <Plus size={24} />
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {keywords.map(kw => (
          <div key={kw} className="bg-blue-50 text-blue-700 px-4 py-2 rounded-full text-sm font-semibold flex items-center space-x-2 border border-blue-100">
            <span>{kw}</span>
            <button onClick={() => removeKeyword(kw)} className="hover:text-blue-900">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ICPConfigurator
