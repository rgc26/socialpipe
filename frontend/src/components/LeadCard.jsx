import React from 'react'
import { ExternalLink, User, Calendar, MessageSquare } from 'lucide-react'

const LeadCard = ({ lead }) => {
  const scoreColor = lead.score >= 80 ? 'text-green-600 bg-green-50' : 
                     lead.score >= 50 ? 'text-yellow-600 bg-yellow-50' : 
                     'text-red-600 bg-red-50'

  return (
    <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all group">
      <div className="flex justify-between items-start mb-3">
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${scoreColor}`}>
          AI Score: {lead.score}
        </span>
        <a 
          href={lead.source_url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-gray-400 hover:text-blue-600 transition-colors"
        >
          <ExternalLink size={16} />
        </a>
      </div>

      <p className="text-sm text-gray-800 line-clamp-3 mb-4 leading-relaxed font-medium">
        {lead.content}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {lead.signal_type && (
          <span className="text-[10px] uppercase tracking-wider font-bold bg-blue-50 text-blue-600 px-2 py-0.5 rounded">
            {lead.signal_type.replace('_', ' ')}
          </span>
        )}
        {lead.urgency && (
          <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded ${
            lead.urgency === 'high' ? 'bg-red-50 text-red-600' : 
            lead.urgency === 'medium' ? 'bg-orange-50 text-orange-600' : 'bg-gray-50 text-gray-600'
          }`}>
            {lead.urgency} Urgency
          </span>
        )}
      </div>

      {lead.pain_point && (
        <div className="mb-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 italic border-l-2 border-blue-400">
          "{lead.pain_point}"
        </div>
      )}

      {lead.outreach_draft && (
        <div className="mb-4 p-3 bg-blue-50/50 rounded-lg text-[11px] text-blue-800 border border-blue-100">
          <p className="font-bold mb-1 flex items-center">
            <MessageSquare size={12} className="mr-1" /> Draft Outreach:
          </p>
          {lead.outreach_draft}
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-50">
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <User size={14} />
          <span className="font-medium truncate max-w-[100px]">{lead.author}</span>
        </div>
        <div className="flex items-center space-x-1 text-xs text-gray-400">
          <Calendar size={14} />
          <span>{new Date(lead.timestamp).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  )
}

export default LeadCard
