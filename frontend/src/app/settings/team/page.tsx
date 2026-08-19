"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Team, TeamMember } from "@/lib/types";

export default function TeamPage() {
  const { user } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [error, setError] = useState("");

  const fetchTeams = async () => {
    try {
      const { data } = await api.get("/api/teams");
      setTeams(data);
      if (data.length > 0 && !selectedTeam) setSelectedTeam(data[0].id);
    } catch { /* empty */ }
    setLoading(false);
  };

  const fetchMembers = async (teamId: string) => {
    try {
      const { data } = await api.get(`/api/teams/${teamId}/members`);
      setMembers(data);
    } catch { /* empty */ }
  };

  useEffect(() => { fetchTeams(); }, []);
  useEffect(() => { if (selectedTeam) fetchMembers(selectedTeam); }, [selectedTeam]);

  const createTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post("/api/teams", { name: teamName });
      setTeams([data, ...teams]);
      setSelectedTeam(data.id);
      setShowCreate(false);
      setTeamName("");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const inviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!selectedTeam) return;
    try {
      await api.post(`/api/teams/${selectedTeam}/invite`, { email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      fetchMembers(selectedTeam);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const removeMember = async (memberId: string) => {
    if (!selectedTeam) return;
    await api.delete(`/api/teams/${selectedTeam}/members/${memberId}`);
    fetchMembers(selectedTeam);
  };

  if (user?.plan !== "team") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Team Workspace</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Team workspaces are available on the Team plan.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Team Workspace</h1>
        <button onClick={() => setShowCreate(!showCreate)} className="btn-primary">
          {showCreate ? "Cancel" : "+ New Team"}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={createTeam} className="mb-6 flex gap-3">
          <input className="input-field flex-1" placeholder="Team name" value={teamName} onChange={e => setTeamName(e.target.value)} required />
          <button type="submit" className="btn-primary">Create</button>
        </form>
      )}

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : teams.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No teams yet. Create one to start collaborating.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Team selector */}
          <div className="space-y-2">
            {teams.map(t => (
              <button key={t.id} onClick={() => setSelectedTeam(t.id)}
                className={`w-full text-left rounded-lg border p-3 ${selectedTeam === t.id ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"}`}>
                <h3 className="font-medium text-slate-900">{t.name}</h3>
                <p className="text-xs text-slate-500">{t.member_count} member{t.member_count !== 1 ? "s" : ""}</p>
              </button>
            ))}
          </div>

          {/* Members */}
          <div className="lg:col-span-2">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Members</h2>

            {/* Invite form */}
            <form onSubmit={inviteMember} className="flex gap-3 mb-4">
              <input className="input-field flex-1" type="email" placeholder="Email address" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} required />
              <select className="input-field w-32" value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
              <button type="submit" className="btn-primary">Invite</button>
            </form>

            <div className="space-y-2">
              {members.map(m => (
                <div key={m.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3">
                  <div>
                    <p className="font-medium text-slate-900">{m.full_name || m.email}</p>
                    <p className="text-xs text-slate-500">{m.email} &middot; {m.role}</p>
                  </div>
                  {m.role !== "owner" && (
                    <button onClick={() => removeMember(m.id)} className="text-xs text-red-600 hover:text-red-800">Remove</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
