'use client';

import React from 'react';
import { Role } from '@/types';
import { ShieldCheck, UserCheck, Briefcase, BarChart3, Landmark, LogOut } from 'lucide-react';

interface NavbarProps {
  currentRole: Role;
  userName: string;
  onLogout: () => void;
  activeTab: 'portal' | 'analytics';
  onTabChange: (tab: 'portal' | 'analytics') => void;
}

const roleConfig = {
  customer: { badge: 'Borrower', icon: <UserCheck className="w-4 h-4 text-emerald-300" /> },
  employee: { badge: 'Loan Officer (Maker)', icon: <Briefcase className="w-4 h-4 text-amber-300" /> },
  manager: { badge: 'Branch Manager (Checker)', icon: <ShieldCheck className="w-4 h-4 text-indigo-300" /> },
};

export const Navbar: React.FC<NavbarProps> = ({ currentRole, userName, onLogout, activeTab, onTabChange }) => {
  // Risk & Audit analytics are visible to officers and managers only
  const canSeeAnalytics = currentRole === 'employee' || currentRole === 'manager';

  return (
    <header className="sticky top-0 z-50 bg-[#0C3B2E] text-white shadow-lg border-b border-[#165443]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onTabChange('portal')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FFBA00] to-[#BB8A52] flex items-center justify-center shadow-md text-[#0C3B2E]">
              <Landmark className="w-6 h-6 stroke-[2.2]" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white">LoanFlow</span>
          </div>

          {/* Navigation Views */}
          {canSeeAnalytics && (
            <nav className="hidden md:flex items-center space-x-2 bg-[#07261d] p-1.5 rounded-xl border border-[#165443]">
              <button
                onClick={() => onTabChange('portal')}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'portal'
                    ? 'bg-[#6D9773] text-white shadow-sm'
                    : 'text-[#8eb494] hover:text-white hover:bg-[#0C3B2E]'
                }`}
              >
                Application Workflow
              </button>
              <button
                onClick={() => onTabChange('analytics')}
                className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'analytics'
                    ? 'bg-[#6D9773] text-white shadow-sm'
                    : 'text-[#8eb494] hover:text-white hover:bg-[#0C3B2E]'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Risk & Audit Analytics</span>
              </button>
            </nav>
          )}

          {/* Signed-in user */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              {roleConfig[currentRole].icon}
              <div className="text-right hidden sm:block">
                <div className="text-xs font-semibold text-white">{userName}</div>
                <div className="text-[10px] text-[#FFBA00] font-medium">{roleConfig[currentRole].badge}</div>
              </div>
            </div>
            <button
              onClick={onLogout}
              title="Sign out"
              className="flex items-center space-x-1 px-2.5 py-1.5 text-xs rounded-lg bg-[#07261d] border border-[#165443] text-[#8eb494] hover:text-white transition-all"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
