"""Render recorded VCD events for review; no production or test inputs change."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];V=R/'validation/handshake_waveform'
events=json.loads((V/'events.json').read_text())['events']
names=['ctl_aw','ctl_ar','ocv','opop','orh','ncv','npop','nrh','old_outstanding','new_outstanding']
fig,axs=plt.subplots(len(names),1,figsize=(13,9),sharex=True,layout='constrained')
for ax,name in zip(axs,names):
 ev=[(t/1000,int(v,2)) for t,n,v in events if n==name and set(v)<=set('01')]
 before=[v for t,v in ev if t<=210];inside=[(t,v) for t,v in ev if 210<t<900]
 data=[(210,before[-1] if before else 0)]+inside
 data.append((900,data[-1][1]))
 ax.step([t for t,v in data],[v for t,v in data],where='post',linewidth=1.7,color='#bd3027' if name in ('ocv','opop','old_outstanding') else '#006d5b')
 ax.set(ylim=(-.2,1.25),yticks=[0,1]);ax.set_xlim(210,900);ax.grid(axis='x',alpha=.25)
 ax.set_ylabel(name,rotation=0,ha='right',va='center',labelpad=10);ax.spines[['top','right']].set_visible(False)
axs[-1].set_xlabel('Recorded simulation time (ns)')
fig.suptitle('Actual RTL VCD: old FIFO pops before AR acceptance; corrected FIFO waits',fontsize=14)
fig.savefig(V/'lost_read.png',dpi=140)
plt.close(fig)
print(V/'lost_read.png')
