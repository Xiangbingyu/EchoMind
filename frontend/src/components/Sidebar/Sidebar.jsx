import React from 'react';
import { FolderKanban, MessageSquare } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export default function Sidebar() {
  return (
    <div className="sidebar">
      <div className="sidebar-avatar">
        {/* 占位头像 */}
        <div className="avatar-placeholder">U</div>
      </div>
      
      <nav className="sidebar-nav">
        <NavLink 
          to="/messages" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <MessageSquare size={24} strokeWidth={1.5} />
          <span>消息</span>
        </NavLink>
        <NavLink 
          to="/workspace" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <FolderKanban size={24} strokeWidth={1.5} />
          <span>Workspace</span>
        </NavLink>
      </nav>
    </div>
  );
}
