p = 'resolve_specs.py'
s = open(p, encoding='utf-8').read()
old = """            zz = zone_for(st.get("zone"), realm) if st.get("zone") else None"""
new = """            if not r.get("marker") and st.get("do") in ("search", "use_item", "drop_item", "travel", "event", "interact"):
                # The walkthrough describes the place by what stands there ("near Merle the Old", "beside Olav",
                # "north of Ardee"): the named NPC's spawn, else the named town/area (wider radius), in that zone.
                text = " ".join(str(st.get(k) or "") for k in ("where", "loc_note", "text"))
                for phrase in sorted(set(re.findall(r"[A-Z][a-z'-]+(?: (?:the |of )?[A-Z][a-z'-]+)*", text)), key=len, reverse=True):
                    if phrase in ("The", "Find", "Search", "Swim", "Use", "Investigate", "Clear", "Wear", "Travel", "Step"): continue
                    hit = find_npc(phrase, st.get("zone"), realm)
                    if hit and hit["same_zone"]:
                        r["marker"] = dict(region=hit["region"], x=hit["x"], y=hit["y"], z=hit["z"])
                        r["anchor"] = f"near {hit['name']} (walkthrough: {st.get('where') or st.get('loc_note') or ''})"
                        break
                if not r.get("marker"):
                    pp = place_point(text, realm)
                    if pp and (not st.get("zone") or (zone_for(st["zone"], realm) or (None, None))[1] == pp["region"]):
                        r["marker"] = dict(region=pp["region"], x=pp["x"], y=pp["y"], z=None)
                        r["anchor"] = f"area centre ({st.get('where') or ''})"
                        r["wide"] = True
            zz = zone_for(st.get("zone"), realm) if st.get("zone") else None"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)

p = 'gen_dataquests.py'
s = open(p, encoding='utf-8').read()
old = """                        'y': m['y'], 'radius': int(sp.get('radius') or 300), 'seconds': int(sp.get('seconds') or 5)}"""
new = """                        'y': m['y'], 'radius': max(int(sp.get('radius') or 300), 1500 if s.get('wide') else 0), 'seconds': int(sp.get('seconds') or 5)}"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
