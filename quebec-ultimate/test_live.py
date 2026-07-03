"""Live test of all modules with REAL HTTP calls - Ghost1o1"""
import sys
sys.path.insert(0, '.')
from modules import get_module_instance


def show(label, m, entity):
    print("=" * 72)
    print(label)
    print("=" * 72)
    r = m.execute(entity)
    print(f"Status: {r.status} | Entities: {len(r.entities_found)} | Rels: {len(r.relationships)}")
    print(f"Sources: {r.sources_hit}")
    if r.warnings:
        print(f"Warnings:")
        for w in r.warnings[:2]:
            print(f"  ! {w[:120]}")
    for e in r.entities_found[:12]:
        v = str(e['value'])[:65]
        print(f"  [{e['type']:18s}] {v:65s} conf={e['confidence']:.2f} ({e['source']})")
    print()


# TEST 2: Email
show("TEST 2: EmailTracer torvalds@linux.foundation (REAL GitHub commit search)",
     get_module_instance(3), {"type": "email", "value": "torvalds@linux.foundation"})

# TEST 3: Phone
show("TEST 3: PhoneIntel +15145550199 (Montreal) - phonenumbers + NANP + DDG",
     get_module_instance(1), {"type": "phone", "value": "+15145550199"})

# TEST 4: Username
show("TEST 4: UsernameSherlock octocat (REAL GitHub API + 25 platform HTTP)",
     get_module_instance(4), {"type": "username", "value": "octocat"})

# TEST 5: Domain
show("TEST 5: DomainMapper github.com (REAL DNS + HackerTarget subfinder)",
     get_module_instance(5), {"type": "domain", "value": "github.com"})

# TEST 6: Name
show("TEST 6: NameResolver 'Linus Torvalds' (REAL GitHub fullname search + DDG)",
     get_module_instance(7), {"type": "name", "value": "Linus Torvalds"})