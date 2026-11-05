import React, { useState, useEffect } from 'react';
import { Building2, HelpCircle, ShieldAlert, Clock, MapPin, Search } from 'lucide-react';
import { Department, HospitalFAQ, HospitalSummary } from '../types';
import { api } from '../services/api';

interface HospitalInfoProps {
  summary: HospitalSummary | null;
}

export const HospitalInfo: React.FC<HospitalInfoProps> = ({ summary }) => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [faqs, setFaqs] = useState<HospitalFAQ[]>([]);
  const [faqSearch, setFaqSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async (query?: string) => {
    setLoading(true);
    try {
      const [deps, faqList] = await Promise.all([
        api.getDepartments(),
        api.getFAQs(query),
      ]);
      setDepartments(deps);
      setFaqs(faqList);
    } catch (e) {
      console.error('Failed to load hospital info:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchFaq = (e: React.FormEvent) => {
    e.preventDefault();
    loadData(faqSearch.trim() || undefined);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Hospital Overview Cards */}
      <div className="lg:col-span-12 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Visiting Hours</p>
            <p className="text-xs text-white mt-0.5 leading-snug">{summary?.visiting_hours || '4:00 PM - 7:00 PM Daily'}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <MapPin className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Hospital Address</p>
            <p className="text-xs text-white mt-0.5 leading-snug">{summary?.address || '742 Evergreen Healthcare Blvd'}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 text-red-400 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium">Emergency Triage</p>
            <p className="text-xs text-red-300 font-bold mt-0.5 leading-snug">Dial 911 / 24/7 Trauma Bay 1</p>
          </div>
        </div>
      </div>

      {/* Departments */}
      <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-800">
          <Building2 className="w-4 h-4 text-sky-400" />
          <h3 className="font-semibold text-sm text-white">Clinical Departments</h3>
        </div>

        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
          {departments.map(dep => (
            <div key={dep.id} className="p-3 bg-slate-950 border border-slate-800/80 rounded-xl space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-white">{dep.name}</span>
                <span className="text-[11px] text-slate-400 font-mono">Ext. {dep.contact_extension}</span>
              </div>
              <p className="text-xs text-slate-400">{dep.description}</p>
              <div className="text-[11px] text-sky-400 pt-1">{dep.floor}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Searchable Knowledge Base / FAQs */}
      <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-sky-400" />
            <h3 className="font-semibold text-sm text-white">Hospital Knowledge Base & Reception FAQs</h3>
          </div>

          <form onSubmit={handleSearchFaq} className="relative w-full sm:w-56">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={faqSearch}
              onChange={(e) => setFaqSearch(e.target.value)}
              placeholder="Search FAQs..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
          </form>
        </div>

        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
          {faqs.map(faq => (
            <div key={faq.id} className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300">
                  {faq.category}
                </span>
                <h4 className="font-medium text-xs text-slate-200">{faq.question}</h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed pl-1">{faq.answer}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
