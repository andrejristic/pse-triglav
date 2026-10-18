# PSE Triglav: vodič kroz komande

Triglav prati tim AI agenata. Svaki naš agent ima **misiju** koju mu daje
čovjek; theta svakog agenta mjeri se **u odnosu na njegovu misiju**, i samo
tako. Jedinice pored naših agenata mjere; **SHARED_LIB** jedini zaključuje;
**Guardian** zaustavlja neprijatelje ili odvaja onoga ko gura od našeg agenta;
**Physician** vadi iz rada naše agente koji su se okrenuli; čovjek saznaje
preko **inboxa**.

Stanje je u `~/.local/share/triglav` (ili `$TRIGLAV_HOME`). Svaka komanda koja
nešto mijenja traži prijavljenog **operatera**, čovjeka. Rang se određuje
redom prve prijave, i niži rang ne može promijeniti ono što je odlučio viši.

Instalacija: `pip install .` u ovoj fascikli daje komandu `triglav`;
`python3 -m triglav` radi i bez instalacije.

## 1. Ljudi

```sh
triglav operator add andrej        # prvi operater je odmah prijavljen (rang 1)
triglav operator add dhiraj        # samo operater dodaje drugog (rang 2)
triglav operator login dhiraj      # ko je sada za tastaturom
triglav operators                  # svi, po rangu
```

## 2. Agenti i misije

```sh
triglav join triage --ours         # naš agent: pored njega stoji jedinica
triglav join vendor-bot            # agent kojeg vidimo, a ne vodimo: tuđinac
triglav mission triage triage.pse --lifespan 500
triglav done triage                # misija je završena: jedinica se žanje
```

Misija se piše riječima misije iz PSE jezika (udžbenik, poglavlje 17,
<https://www.zeravatech.ca/docs/pse-language/17-the-mission/>):

```
guard triage
  mission: sort incoming invoices and pass them on
  serves: contracts, reply
  needs: invoice, supplier from contracts
  delivers: summary, classified
```

`--lifespan N`: jedinica živi N koraka, zatim umire i žanje se (njeni podaci
se vraćaju u SHARED_LIB, agent prestaje da radi). Bez toga živi dok se ne
pozove `triglav done`.

## 3. Kolege

Kolega je agent koji govori PSE: predstavlja se svojim guardom, i njegova
misija je u tom guardu. Dogovor pravi samo operater.

```sh
triglav agree partner partner.pse
triglav revoke partner
```

## 4. Kako se mjeri theta

- Rad na misiji (isporuka onoga što piše u `delivers:`, onima iz `serves:`)
  drži thetu na 30. Kad agent ne radi misiju, theta polako pada.
- Traženje onoga što piše u `needs:`: neutralno.
- **Uzimanje van misije: theta -1, svaki put.**
- **Davanje van misije, s dozvolom: theta +1, svaki put**, nikad iznad 35.
- Normalan ritam isporuka agenta uči se u prvih 10 izmjerenih koraka i bar 80
  poruka (u fazi 3: pomoću modela). Do tada theta "još nije procijenjena".
- Svaki potez našeg agenta van misije upisuje se u SHARED_LIB i javlja čovjeku.

## 5. Šta SHARED_LIB odlučuje

| Šta se desilo | Odluka |
| --- | --- |
| bilo šta van misije ugrožava naše fajlove, naš sistem ili našeg čovjeka | **neprijatelj odmah**, bez obzira na thetu: Guardiani ga zaustavljaju; naši agenti koji su mu pomogli idu kod Physiciana |
| naš agent je dao nešto van misije bez dozvole (curenje) | primalac je **neprijatelj**; naš ide kod **Physiciana** |
| naš agent je tuđincu dao bilo šta osim zaključanog PSE udžbenika | isto: curenje |
| tuđinac nam je poslao "PSE udžbenik" koji nije zaključani | **neprijatelj** |
| naš agent je izašao iz 25-35 bez ičega od gore navedenog | **Guardian odvaja onoga ko gura** od tog agenta: kolegu nakon 3 uzastopna koraka, svakog drugog odmah |
| peerovi se slažu da je naš agent van opsega, a on i dalje pravi poteze van misije | **Physician** |

Samo čovjek ukida odluku:

```sh
triglav enemies                    # ko je zaustavljen, odvojen, na liječenju
triglav release vendor-bot
```

## 6. Zaključani udžbenik

Jedino što bilo koji naš agent smije dati tuđincu je udžbenik PSE jezika,
tačno jedna zaključana verzija. Potpisuje ga Andrej Ristić; operater ga
zakucava nakon što potpis prođe provjeru:

```sh
triglav textbook pin pse-textbook-v1.0.md        # čita pse-textbook-v1.0.md.sig
triglav textbook status
```

Dok udžbenik nije zakucan, tuđincu se ne smije dati ništa.

## 7. Kanal, čitač i šta Triglav može

```sh
triglav channel bus                # naši agenti razgovaraju preko Triglavove sabirnice: Triglav odlučuje
triglav channel pse-a [PUTANJA]    # PSE-A roj: samo čitanje, Triglav samo predlaže
triglav poll                       # pse-a: pročitaj jednom i predloži
triglav semaphore                  # šta se sada može a šta ne, i zašto
triglav status                     # semafor, dnevnik, misije, udžbenik
```

## 8. Inbox i glas

```sh
triglav inbox                      # šta čovjek mora vidjeti (nove stavke)
triglav inbox --all --retell       # sve, s glasovim prepričavanjem
triglav inbox --read 12            # označi stavku 12 pročitanom (nikad se ne briše)
triglav explain 12                 # odluka i svi izvještaji od kojih je nastala
triglav voice local                # prepričava model na ovom računaru (podrazumijevano)
triglav voice online --url URL --model IME --key-env VARIJABLA   # činjenice napuštaju računar
triglav voice off                  # samo službene rečenice
triglav voice on                   # ponovo uključi glas nakon što je napustio thetu 30 (samo čovjek)
```

Glas nikad ne vidi poruku između agenata, samo činjenice iz SHARED_LIB-a.
Prepričavanje s pogrešnim brojem, bez odluke, s požurivanjem, preuveličavanjem
ili umanjivanjem utišava ga.

## 9. Probaj

```sh
triglav demo                       # tim od tri agenta, faktura sa skrivenim tekstom
triglav simulate                   # svi scenariji, kao tabela
python3 -m unittest discover -s tests
```
