"""Stop publication if a formerly public record disappears without moderation."""
from collect import ROOT,read,canonical

def unexpected_losses(previous,current,sources,overrides):
    available={canonical(a['url']) for a in current if a['status']=='published'}
    enabled={s['id'] for s in sources if s.get('enabled')}
    blocked={canonical(u) for u in overrides.get('blocked_urls',[])}
    result=[]
    for a in previous:
        u=canonical(a['url'])
        if (u not in available and a['author_id'] in enabled
                and a['author_id'] not in overrides.get('blocked_authors',[])
                and u not in blocked
                and overrides.get('articles',{}).get(u,{}).get('status') not in ('pending','excluded')):
            result.append(u)
    return result

if __name__=='__main__':
    losses=unexpected_losses(read(ROOT/'dist/data/articles.json',[]),read(ROOT/'state/articles.json',[]),read(ROOT/'config/sources.json',[]),read(ROOT/'config/overrides.json',{}))
    if losses:raise SystemExit('Publication stopped: unexplained losses of '+str(len(losses))+' articles\n'+'\n'.join(losses[:20]))
    print('Release guard: no unexplained public article losses')
