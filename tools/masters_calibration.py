import statistics as st, math
from scipy.stats import t as T, norm
brk=[49.5,-3.4,13.3,77.8,19.4,-4.6,80.5,8.1,-2.5,-48.7,2.5,129.3,46.8,14.5,102.5,32.8,31.8,38.4,69.0,-2.7,93.7,14.2,4.6,59.3,84.6,-23.1,35.6,29.8,38.9,25.0,
57.4,6.2,34.9,52.2,-19.9,26.6,6.5,-3.8,15.8,4.3,0.8,24.1,28.7,-31.8,2.7,21.4,-4.7,16.8,32.7,27.0,-12.5,23.4,21.9,2.8,11.0,2.4,29.6,4.0,15.8,25.5,10.9]
spx=[10.0,-11.7,30.9,11.0,-8.4,3.9,14.6,18.9,-14.8,-26.4,37.2,23.6,-7.4,6.4,18.2,32.3,-5.0,21.4,22.4,6.1,31.6,18.6,5.1,16.6,31.7,-3.1,30.5,7.6,10.1,1.3,
37.6,23.0,33.4,28.6,21.0,-9.1,-11.9,-22.1,28.7,10.9,4.9,15.8,5.5,-37.0,26.5,15.1,2.1,16.0,32.4,13.7,1.4,12.0,21.8,-4.4,31.5,18.4,28.7,-18.1,26.3,25.0,17.9]
assert len(brk)==len(spx)==61
def tstat(x):
    n=len(x); m=st.mean(x); s=st.stdev(x); tt=m/s*math.sqrt(n)
    z=norm.isf(T.sf(tt,n-1)) if tt>0 else -norm.isf(T.cdf(tt,n-1))
    return dict(n=n,mean=round(m,2),sd=round(s,2),t=round(tt,2),z=round(z,2))
ex=[a-b for a,b in zip(brk,spx)]
yrs=list(range(1965,2026))
print('excess 1965-2025',tstat(ex))
print('raw 1965-2025',tstat(brk))
for a,b in [(1965,1990),(1991,2025),(2001,2025),(2011,2025)]:
    print('excess',a,b,tstat([e for e,y in zip(ex,yrs) if a<=y<=b]))
print('beat years',sum(e>0 for e in ex),'/61')
print('bar N:',{N:round(norm.isf(norm.sf(2)/N),2) for N in (1,10,100,1000,10000,47248)})
net=[9.04,-3.20,58.24,39.44,33.60,39.12,70.72,38.32,31.52,21.20,41.68,24.48,98.48,33.02,25.82,21.90,24.92,29.51,44.30,73.42,82.38,38.98,29.40,37.02,29.01,46.93,39.20,36.01,35.62,45.02,39.98]
gross=[16.3,1.0,77.8,54.3,47.0,53.9,93.4,52.9,44.4,31.5,57.1,35.6,128.1,56.6,51.1,44.1,49.5,57.7,84.1,136.1,152.1,74.6,57.5,71.1,56.8,88.8,75.0,69.3,68.6,85.4,76.4]
sp=[s for s,y in zip(spx,yrs) if 1988<=y<=2018]
print('MED net raw',tstat(net)); print('MED net excess',tstat([a-b for a,b in zip(net,sp)])); print('MED gross excess',tstat([a-b for a,b in zip(gross,sp)]))
for k in (5,10):
    print('MED net excess first',k,'yrs',tstat([a-b for a,b in zip(net[:k],sp[:k])]))
print('S&P itself 1965-2025 raw', tstat(spx))
import numpy as np
def alpha(y,x):
    y=np.array(y);x=np.array(x);X=np.c_[np.ones(len(x)),x];b,res,_,_=np.linalg.lstsq(X,y,rcond=None)
    e=y-X@b;n=len(y);s2=e@e/(n-2);cov=s2*np.linalg.inv(X.T@X);ta=b[0]/np.sqrt(cov[0,0])
    z=norm.isf(T.sf(ta,n-2)) if ta>0 else -norm.isf(T.cdf(ta,n-2))
    return dict(alpha=round(b[0],2),beta=round(b[1],2),t=round(ta,2),z=round(z,2),n=n)
print('BRK alpha 1965-2025',alpha(brk,spx))
print('BRK alpha 2001-2025',alpha(brk[36:],spx[36:]))
print('MED net alpha',alpha(net,sp)); print('MED gross alpha',alpha(gross,sp))
