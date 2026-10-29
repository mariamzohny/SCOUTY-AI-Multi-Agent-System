let currentJobs = [];
let currentFilter = "All";

document.addEventListener("DOMContentLoaded", () => {
    initAuth();

    // Search event
    document.getElementById("search-input").addEventListener("input", filterJobs);

    // Filters
    document.getElementById("status-select").addEventListener("change", filterJobs);
    document.getElementById("type-select").addEventListener("change", filterJobs);

    // Score slider
    const slider = document.getElementById("score-slider");
    const scoreVal = document.getElementById("score-val");
    slider.addEventListener("input", (e) => {
        scoreVal.textContent = e.target.value + "%";
        filterJobs();
    });

    // Top navigation tabs
    document.querySelectorAll(".nav-tab").forEach(tab => {
        tab.addEventListener("click", (e) => {
            e.preventDefault();
            document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            currentFilter = tab.dataset.filter;
            
            // Sync dropdown if Tab selected Job or Internship
            document.getElementById("type-select").value = (currentFilter === "Job" || currentFilter === "Internship") ? currentFilter : "All";
            document.getElementById("status-select").value = "All";
            
            filterJobs();
        });
    });

    // Action buttons
    document.getElementById("btn-scrape").addEventListener("click", triggerScrape);
    document.getElementById("live-search-form").addEventListener("submit", async (e) => {e.preventDefault(); await liveSearch(document.getElementById("live-search").value);});
    document.getElementById("btn-profile").addEventListener("click", ()=>document.getElementById("profile-dialog").showModal());
    document.getElementById("profile-close").addEventListener("click", ()=>document.getElementById("profile-dialog").close());
    document.getElementById("cv-upload-form").addEventListener("submit",uploadCV);
    document.getElementById('download-cv').addEventListener('click',downloadCV);
    document.getElementById("profile-form").addEventListener("submit",saveProfile);
    document.getElementById("btn-logout").addEventListener("click",async()=>{await api('/api/logout',{method:'POST'});location.reload()});
});

async function fetchProfile() {
    try {
        const profile = await api("/api/profile");
        
        const skillsContainer = document.getElementById("profile-skills-list");
        skillsContainer.innerHTML = (profile.skills||[]).map(s => `<span class="skill-chip">${escapeHtml(s)}</span>`).join("");
        const h=skillsContainer.parentElement; const label=h.querySelector('.candidate-name'); if(label)label.textContent=profile.name||'Your profile';
        fillProfile(profile);
    } catch (err) {
        console.error("Error fetching profile:", err);
    }
}

async function fetchStats() {
    try {
        const stats = await api("/api/stats");
        document.getElementById("stat-total").textContent = stats.total_jobs;
        document.getElementById("stat-internships").textContent = stats.total_internships;
        document.getElementById("stat-junior").textContent = stats.total_junior_jobs;
        document.getElementById("stat-high").textContent = stats.high_matches;

        document.getElementById("badge-total").textContent = stats.total_jobs;
        document.getElementById("badge-internships").textContent = stats.total_internships;
        document.getElementById("badge-junior").textContent = stats.total_junior_jobs;
        document.getElementById("badge-high").textContent = stats.high_matches;
        document.getElementById("badge-saved").textContent = stats.saved_count;
        document.getElementById("badge-applied").textContent = stats.applied_count;
    } catch (err) {
        console.error("Error fetching stats:", err);
    }
}

async function fetchJobs() {
    try {
        currentJobs = await api("/api/jobs");
        filterJobs();
    } catch (err) {
        console.error("Error fetching jobs:", err);
    }
}

function filterJobs() {
    const query = document.getElementById("search-input").value.toLowerCase();
    const statusSelect = document.getElementById("status-select").value;
    const typeSelect = document.getElementById("type-select").value;
    const minScore = parseInt(document.getElementById("score-slider").value, 10);

    const filtered = currentJobs.filter(item => {
        const j = item.job;
        if (!j.is_open) return false;

        const isInternship = j.job_type === "Internship" || j.title.toLowerCase().includes("intern");

        const matchesQuery = !query || 
            j.title.toLowerCase().includes(query) || 
            j.company.toLowerCase().includes(query) || 
            j.description.toLowerCase().includes(query) ||
            item.matched_skills.some(s => s.toLowerCase().includes(query));

        const matchesMinScore = item.score >= minScore;
        
        let matchesNav = true;
        if (currentFilter === "Internship") matchesNav = isInternship;
        else if (currentFilter === "Job") matchesNav = !isInternship;
        else if (currentFilter === "High") matchesNav = item.score >= 70;
        else if (currentFilter === "Saved") matchesNav = item.status === "Saved" || item.saved;
        else if (currentFilter === "Applied") matchesNav = item.status === "Applied" || item.applied;

        let matchesDropdownStatus = true;
        if (statusSelect !== "All") matchesDropdownStatus = item.status === statusSelect;

        let matchesDropdownType = true;
        if (typeSelect === "Internship") matchesDropdownType = isInternship;
        else if (typeSelect === "Job") matchesDropdownType = !isInternship;

        return matchesQuery && matchesMinScore && matchesNav && matchesDropdownStatus && matchesDropdownType;
    });

    renderJobs(filtered);
}

function renderJobs(jobs) {
    const container = document.getElementById("jobs-container");
    if (!jobs || jobs.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 50px; color: var(--text-muted);">
                <i class="fa-solid fa-folder-open" style="font-size: 36px; margin-bottom: 12px; color: var(--accent-cyan);"></i>
                <p style="font-size: 15px; font-weight: 600;">No active openings found matching criteria.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = jobs.map(item => {
        const j = item.job;
        let scoreClass = "score-low";
        if (item.score >= 80) scoreClass = "score-high";
        else if (item.score >= 65) scoreClass = "score-med";

        const isSaved = item.status === "Saved" || item.saved;
        const isApplied = item.status === "Applied" || item.applied;
        const isInternship = j.job_type === "Internship" || j.title.toLowerCase().includes("intern");

        const typeBadge = isInternship 
            ? `<span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: rgba(99, 102, 241, 0.25); color: #a5b4fc; font-weight: 700; margin-left: 6px;"><i class="fa-solid fa-user-graduate"></i> INTERNSHIP</span>`
            : `<span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: rgba(6, 182, 212, 0.25); color: #67e8f9; font-weight: 700; margin-left: 6px;"><i class="fa-solid fa-briefcase"></i> JOB</span>`;

        // Strip any emojis from reasoning text
        const cleanReasoning = item.reasoning.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '');

        return `
            <div class="job-card glass">
                <div class="job-header">
                    <div>
                        <div class="job-title">
                            ${escapeHtml(j.title)} ${typeBadge}
                        </div>
                        <div class="company-name"><i class="fa-solid fa-building"></i> ${escapeHtml(j.company)} • ${escapeHtml(j.source)}</div>
                    </div>
                    <div class="score-badge ${scoreClass}">
                        <i class="fa-solid fa-microchip"></i> ${item.score}%
                    </div>
                </div>

                <div class="reasoning-box">
                    ${escapeHtml(cleanReasoning)}
                </div>

                <div class="matched-skills">
                    ${item.matched_skills.map(s => `<span class="skill-chip">${escapeHtml(s)}</span>`).join("")}
                </div>

                <div class="job-footer">
                    <div class="job-meta">
                        <i class="fa-solid fa-location-dot"></i> ${escapeHtml(j.location)}<br>
                        <i class="fa-solid fa-clock"></i> ${escapeHtml(j.posted_date)}
                    </div>
                    <div class="job-actions">
                        <button class="btn-icon ${isSaved ? 'active-saved' : ''}" onclick="toggleStatus('${encodeURIComponent(j.id)}', '${isSaved ? 'New' : 'Saved'}')" title="Save Listing">
                            <i class="fa-solid fa-bookmark"></i>
                        </button>
                        <button class="btn-icon ${isApplied ? 'active-applied' : ''}" onclick="toggleStatus('${encodeURIComponent(j.id)}', '${isApplied ? 'New' : 'Applied'}')" title="Mark Applied">
                            <i class="fa-solid fa-paper-plane"></i>
                        </button>
                        <a href="${safeUrl(j.url)}" target="_blank" rel="noopener noreferrer" class="btn-icon" title="Apply Now">
                            <i class="fa-solid fa-external-link"></i>
                        </a>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

async function toggleStatus(jobId, newStatus) {
    try {
        await api(`/api/jobs/${jobId}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus })
        });
        showToast(`Status updated to ${newStatus}`);
        await fetchJobs();
        await fetchStats();
    } catch (err) {
        console.error("Error updating status:", err);
    }
}

async function liveSearch(query) {
    const msg=document.getElementById('search-message');
    msg.textContent='Searching the provider for real listing links...';
    const link=document.getElementById('provider-link');
    try {
      const data=await api('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,source:document.getElementById('job-source').value})});
      link.href=safeUrl(data.search_url);const sourceLabels={remotive:'Open Remotive',remoteok:'Open Remote OK',arbeitnow:'Open Arbeitnow',himalayas:'Open Himalayas',all:'Browse Himalayas'};link.textContent=sourceLabels[document.getElementById('job-source').value]||'Browse source';
      msg.textContent = data.message || (data.ok ? 'Search complete.' : 'No matching jobs found.');
      if (!data.ok && data.status === 'provider_error') {
        showToast('The job provider could not be reached. See the detailed error above.');
      } else if (!data.ok && data.status === 'no_matches') {
        showToast('Connection succeeded, but no relevant jobs matched this search.');
      }
      // Apply the same search term to the visible cards as an extra safeguard.
      document.getElementById('search-input').value='';
      await fetchJobs(); await fetchStats();
    } catch(e) {msg.textContent=e.message;showToast(e.message)}
}
document.querySelectorAll('.quick-search button').forEach(button=>button.addEventListener('click',()=>{document.getElementById('live-search').value=button.dataset.query;liveSearch(button.dataset.query)}));
async function triggerScrape(){await liveSearch(document.getElementById('live-search').value.trim()||'Data Science Intern')}
function showToast(msg) {
    const toast = document.getElementById("toast");
    document.getElementById("toast-msg").textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}

function escapeHtml(text){return String(text??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function safeUrl(url){try{const p=new URL(url);return p.protocol==='https:'?p.href:'#'}catch(e){return '#'}}
async function api(path, options={}){
  const res=await fetch(path,options);let data={};try{data=await res.json()}catch{}
  if (!res.ok){const detail=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||'Request failed');throw new Error(detail)}
  return data;
}
let authMode='login';
async function initAuth(){
  document.getElementById('auth-form').addEventListener('submit', async e=>{
    e.preventDefault(); const email=document.getElementById('auth-email').value;const password=document.getElementById('auth-password').value;
    try{await api('/api/'+authMode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});await showApp()}
    catch(err){document.getElementById('auth-error').textContent=err.message}
  });
  document.getElementById('toggle-auth').addEventListener('click',()=>{
    authMode=authMode==='login'?'register':'login';
    document.getElementById('auth-title').textContent=authMode==='login'?'Sign in':'Create account';
    document.getElementById('auth-submit').textContent=authMode==='login'?'Sign in':'Register';
    document.getElementById('toggle-auth').textContent=authMode==='login'?'Create an account instead':'Already registered? Sign in';
    document.getElementById('auth-error').textContent='';
  });
  try{await api('/api/profile');await showApp()}catch{}
}
async function showApp(){document.getElementById('auth-screen').classList.add('hidden'); await Promise.all([fetchProfile(),fetchStats(),fetchJobs()]);}
function fillProfile(profile){
 const form=document.getElementById('profile-form');
 for(const el of form.elements){if(!el.name)continue;const value=profile[el.name];el.value=Array.isArray(value)?value.join(', '):value??''}
}
async function saveProfile(e){
 e.preventDefault();const form=e.currentTarget;const values=Object.fromEntries(new FormData(form).entries());
 for(const k of ['skills','languages']) values[k]=(values[k]||'').split(',').map(x=>x.trim()).filter(Boolean);
 values.years_experience=Number(values.years_experience||0);
 try{const current=await api('/api/profile');await api('/api/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...current,...values})});document.getElementById('profile-message').textContent='Saved! Match scores refreshed.';await fetchProfile();await fetchJobs();await fetchStats()}
 catch(err){document.getElementById('profile-message').textContent=err.message}
}
async function uploadCV(e){e.preventDefault();const file=document.getElementById('cv-file').files[0];if(!file){document.getElementById('profile-message').textContent='Please choose a CV file first.';return;}const body=new FormData();body.append('file',file);
 try{const data=await api('/api/profile/upload',{method:'POST',body});fillProfile(data.profile);document.getElementById('profile-message').textContent=data.message;await fetchProfile();await fetchJobs();await fetchStats()}
 catch(err){document.getElementById('profile-message').textContent=err.message}
}

async function downloadCV(e){
 e.preventDefault();const message=document.getElementById('profile-message');
 message.textContent='Preparing your PDF...';
 try{
  const res=await fetch('/api/profile/download',{credentials:'same-origin'});
  if(!res.ok){let error='PDF download failed ('+res.status+')';try{const data=await res.json();error=data.detail||error}catch{}throw new Error(error)}
  const blob=await res.blob();
  if(!blob.size || !res.headers.get('content-type')?.includes('application/pdf'))throw new Error('Server did not return a valid PDF.');
  const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='scouty_cv.pdf';document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);message.textContent='CV PDF downloaded.';
 }catch(err){message.textContent=err.message;showToast(err.message)}
}
