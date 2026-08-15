# Chemical significance: groups, rings, and target classes

"What is significant about this functional group?" almost never wants the group's name
expanded. It wants the group's *role*: what it can do chemically, what it costs to carry,
and therefore what its presence predicts about where the molecule will sit and how it
will behave. That last part is what makes the answer checkable instead of decorative.

This file is three tables and two pieces of prose. Use it to convert a structural
observation into a claim someone can test, and then into an `Implication` with a real
`if_wrong`.

**Read the tables as directions, not values.** Everything here is qualitative on purpose.
Charge state, hydrogen-bond strength, metabolic fate and permeability all depend on the
local environment — neighbouring substituents, the dielectric of the site, the assay
buffer, the species. No numbers appear below because a number stated without its
measurement conditions is worse than a direction stated honestly. Where a claim is
genuinely context-dependent, the table says so rather than asserting the common case
flatly.

---

## Table 1 — Functional groups

| Group | Contributes to binding | Costs | What its presence predicts about placement |
|---|---|---|---|
| **Carbonyl (C=O)** | A strong, directional hydrogen-bond acceptor at the oxygen lone pairs; polarises the adjacent carbon. | Little in itself; the adjacent carbon is electrophilic, which in some contexts is a reactivity or metabolic handle. | The oxygen points at a donor — a backbone NH, a serine, threonine or tyrosine hydroxyl, a lysine or arginine nitrogen, or an ordered water. Expect it at the polar rim rather than in the middle of a greasy pocket. |
| **Carboxylic acid** | Usually ionised at physiological pH, so a full negative charge plus a bidentate acceptor pair. Makes salt bridges to arginine and lysine and coordinates metals. | A large permeability penalty: poor passive membrane crossing, poor brain penetration, and glucuronidation as a clearance route. Reaching an intracellular target becomes a real problem. | It pairs with a basic residue or a metal, generally near the solvent-exposed mouth of the site rather than deep inside. A fully buried carboxylate with no counter-charge is strong evidence that the pose or the protonation assignment is wrong. |
| **Primary amine (–NH₂)** | Cationic in most physiological contexts; up to three donor hydrogens plus a charge. Good for salt bridges to aspartate and glutamate, and for cation–π against an aromatic face. | Strong permeability penalty; a frequent source of off-target liability when hung on a lipophilic core; oxidative deamination as a clearance route. | An acidic residue or an aromatic cage. Because it is small and has three donors, it tolerates several orientations, so it constrains position more tightly than it constrains rotation. |
| **Secondary amine (–NHR)** | Cationic like the primary, with one fewer donor hydrogen and more steric shielding. Often also the synthetic joint between two halves of a molecule. | Similar permeability penalty; in some substitution patterns a nitrosamine-formation concern, which is currently a live regulatory issue. | The same acidic or aromatic features, but with a defined direction, because the two substituents fix the geometry of the remaining N–H. That directionality is a checkable pose constraint the primary amine does not give you. |
| **Tertiary amine (–NR₂R₃)** | When protonated, a well-shielded positive charge with a single donor hydrogen. The standard basic centre used to make a lipophilic scaffold soluble as a salt. | Permeability; recurring cardiac ion-channel liability in basic lipophilic molecules; lysosomal trapping; N-dealkylation and N-oxidation as clearance routes. | An acidic residue or an aromatic cage, and the charge tolerates partial solvent exposure better than burial. If a pose puts a protonated tertiary amine against a hydrophobic wall with no counter-charge, doubt the pose. |
| **Amide (–C(=O)N–)** | A donor and an acceptor in one near-planar rigid unit, so it can bridge two pocket features at fixed spacing. Restricted rotation lowers the conformational entropy cost of binding. | Adds polar surface area, so passive permeability falls; a secondary amide's NH raises the desolvation penalty badly if it ends up unpaired. Amidase hydrolysis matters in some contexts but amides are generally far more stable than esters. | It imitates a protein backbone's hydrogen-bonding pattern, so look for it pairing with a backbone carbonyl and NH along a strand or at the hinge of a site. An unpaired amide NH in a pose is a genuine energetic objection, not a cosmetic one. |
| **Sulfonamide (–SO₂N–)** | Tetrahedral sulfur with two acceptor oxygens, and an unusually acidic donor if the nitrogen carries a hydrogen. The geometry is quite unlike a carboxamide, so it is not a simple isostere of one. | High polarity and often poor permeability. A primary aryl sulfonamide binds carbonic anhydrases strongly, which is a well-known selectivity liability. Sulfa-type hypersensitivity is a concern for certain patterns. | The oxygens engage a donor pair or a cationic residue, and the tetrahedral centre places its substituents at roughly right angles, so a sulfonamide typically occupies a corner or a branch point in a site rather than a straight channel. |
| **Hydroxyl (–OH)** | Donor and acceptor at once, at almost no steric cost. A phenol is more acidic and a stronger participant than an aliphatic alcohol. | A prime conjugation site — glucuronidation and sulfation — so it is frequently the reason a compound clears quickly. Adds polar surface area. | A polar contact, and often one mediated by a conserved water rather than made directly to the protein. A hydroxyl that appears to point at nothing is therefore often correct, which is the opposite of the usual reading. |
| **Ether (–O–)** | A weak acceptor with no donor. Both lone pairs are sterically shielded, so ether oxygens accept far less readily than carbonyl oxygens. Mostly used to insert a link without paying much polarity. | Modest, though benzylic ethers and methylenedioxy groups are metabolic soft spots and O-dealkylation is a common clearance route. | It contributes geometry rather than a contact, so do not treat an ether oxygen as an anchor. Expect it lying along a channel wall, setting the vector between the pieces it joins. |
| **Fluorine (–F)** | An unusual case. Small enough to replace hydrogen with almost no steric cost, strongly electron-withdrawing, and in practice a very poor hydrogen-bond acceptor. Used to block a metabolic site, tune the basicity of a nearby amine, or bias a conformation. | Little steric or solubility cost singly; lipophilicity rises when several are added; it can shift a nearby pKa enough to change the molecule's charge state, which changes everything else. | Fluorine usually marks a position that *was being metabolised*, not a position that is binding. When you see one, ask what it was blocking before you ask what it contacts. |
| **Chlorine, bromine, iodine** | Substantial hydrophobic bulk with a polarisable electron cloud, plus the possibility of a genuine halogen bond in which the σ-hole accepts electron density from a carbonyl oxygen or other acceptor. Strength rises Cl < Br < I. | Lipophilicity and molecular weight climb quickly and solubility falls. Aryl halides can be metabolic and toxicological flags in some series. Iodine rarely survives into a final compound. | A hydrophobic subpocket. If a halogen bond is being claimed, the geometry is highly directional — the acceptor should lie close to linear with the C–X bond — which is one of the sharpest checkable constraints available on a pose. |
| **Nitrile (–C≡N)** | A linear, slim, weak acceptor at nitrogen that fits where a carbonyl cannot. Also a mild electrophile capable of reversible covalent bonding to an active-site cysteine or serine in the right setting. | Generally well tolerated on an aromatic ring; some aliphatic nitriles raise a metabolic cyanide-release concern. | A narrow channel or a small polar niche. Its linearity means it cannot bend around anything, so a nitrile in a pose must have a straight line of sight to whatever it engages. |
| **Nitro (–NO₂)** | Strongly electron-withdrawing, two acceptor oxygens, coplanar with an attached ring. | A genuine liability flag. Nitroaromatics can be reduced to reactive intermediates and carry a mutagenicity association, so they are usually engineered out even when they bind well. | It will engage a donor or a cation, but its more useful prediction is about the compound's provenance: a nitro group usually means a tool compound or an unoptimised screening hit rather than a lead. |
| **Trifluoromethyl (–CF₃)** | Compact, very lipophilic, metabolically inert bulk. Roughly isopropyl-sized with quite different electronics; almost never an acceptor. | Raises lipophilicity and molecular weight, lowers solubility. | A hydrophobic pocket, and typically a position where a methyl group was being oxidised. Like fluorine, it is often better read as a metabolic fix than as a binding element. |
| **Phenyl (–C₆H₅)** | A flat, rigid hydrophobic surface that engages π-stacking with phenylalanine, tyrosine, tryptophan and histidine, face-to-face and edge-to-face. Frequently a scaffold anchor as much as a binding group. | Lipophilicity and flatness. Many flat aromatic rings make a molecule crystalline and poorly soluble; unsubstituted positions invite aromatic hydroxylation. | An aromatic-lined subpocket, with the ring roughly parallel or roughly perpendicular to its partner rather than at an arbitrary angle — a geometric constraint worth checking in any pose that claims stacking. |
| **Pyridine nitrogen** | Turns a phenyl into a good directional acceptor at one defined ring position with little change in shape, and lowers lipophilicity. Weakly basic, usually neutral at physiological pH. Coordinates heme iron. | The classic cost is cytochrome P450 inhibition by direct iron coordination, making an accessible pyridine nitrogen a drug-drug interaction flag. | The nitrogen points at a donor, and the ring fixes that direction, so a pyridine nitrogen buried against a hydrophobic wall is good evidence the ring is flipped in the pose. If a heme is present, test coordination explicitly. |
| **Imidazole** | Two nitrogens with different roles, one donor and one acceptor, on a small aromatic ring. Coordinates metals strongly, especially zinc and heme iron. Can be neutral or cationic near physiological pH. | A strong P450 inhibition liability, and often the reason an azole-like compound has broad interaction problems. | A metal if one is present; otherwise a donor–acceptor pair at close range. Because it tautomerises, treat both tautomers as separate poses to enumerate rather than picking one — this is a common silent error. |
| **Thiol (–SH)** | A soft, polarisable donor that coordinates metals extremely well, zinc above all. | Readily oxidised, forms disulfides, and rarely survives into a drug outside a few specific classes. | A metal, almost always. A free thiol in the ligand and a zinc in the site is one of the more reliable placement predictions in this table. |
| **Thioether (–S–)** | Larger, more polarisable and more lipophilic than an ether; a very weak acceptor. | Readily oxidised to sulfoxide and sulfone by cytochromes and flavin monooxygenases, and the oxidation changes both shape and polarity substantially. | A hydrophobic contact rather than a hydrogen bond. Its second, more practical prediction: if a compound has an unexplained metabolite, this is where to look first. |
| **Ester (–C(=O)O–)** | A carbonyl acceptor plus an ether oxygen in a near-planar arrangement. | The dominant biological fact about an ester is that esterases hydrolyse it, often fast. An ester is therefore either a deliberate prodrug or a stability problem. | The carbonyl oxygen makes the contact. More usefully, its presence predicts that what circulates may be the acid, so a binding model built on the ester may be modelling a molecule that is not there. |
| **Ketone (–C(=O)–)** | A carbonyl acceptor flanked by hydrophobic substituents on both sides, with no donor. | Reduced to the alcohol by carbonyl and aldo-keto reductases; reactive enough in some contexts to form covalent adducts. | The oxygen at a donor with the flanking groups filling hydrophobic space, so a ketone often sits precisely at a junction between a polar spot and a greasy one. |
| **Urea (–NH–C(=O)–NH–)** | Two donor NH groups flanking one acceptor carbonyl, held nearly planar: a matched donor–acceptor–donor array at fixed spacing, which is a strong and geometrically specific recognition element. | High melting point, low solubility, often poor permeability. Symmetrical ureas are notoriously insoluble. | It pairs with a complementary acceptor–donor–acceptor arrangement, commonly a backbone stretch or a pair of acidic side chains. A urea persisting through a series usually means the chemists found a multi-point interaction they were unwilling to give up. |
| **Phosphate (–OPO₃)** | Multiple acceptors on a doubly charged, heavily hydrated group. | Essentially no passive permeability, so a phosphate-bearing compound is an endogenous-like species that uses a transporter, an extracellular agent, or the cleaved form of a prodrug. | A dedicated strongly basic recognition site: a cluster of arginines and lysines, a metal, or a glycine-rich loop. If the pocket has no such feature, the pose is wrong, and this is one of the few placement predictions strong enough to reject a pose outright. |
| **Boronic acid (–B(OH)₂)** | Forms a reversible covalent tetrahedral adduct with a nucleophilic serine, threonine or catalytic residue, behaving as a transition-state mimic rather than an ordinary binder. | Unusual stability and formulation problems, off-target reactivity with any accessible nucleophile, and a mechanism that makes conventional non-covalent docking scores meaningless. | A specific nucleophilic residue in a catalytic site. It also predicts time-dependent binding, which changes how any measurement of it should be interpreted and which equilibrium constants are meaningful at all. |

---

## Table 2 — Ring systems and scaffolds

| Ring system | Shape and rigidity | Commonly engages | What it signals about the series |
|---|---|---|---|
| **Benzene** | Flat, rigid, six-membered, no accessible lone pairs. | Aromatic side chains face-to-face and edge-to-face; hydrophobic walls. | A core or a spacer. If a series varies only in benzene substitution, the team has concluded the ring position is fixed and is exploring the vectors out of it. |
| **Pyridine** | Same shape and rigidity as benzene, with one directional acceptor and lower lipophilicity. | A donor at the nitrogen; heme iron. | A deliberate polarity or solubility fix that preserves shape, or an attempt to pick up one specific hydrogen bond. Also an unresolved P450 interaction question that someone should have asked. |
| **Pyrimidine** | Flat, with nitrogens at the 1 and 3 positions presenting a donor–acceptor pattern that mimics a nucleobase edge. | Backbone donor–acceptor pairs at a hinge; nucleotide sites. | Strongly suggests a nucleotide-binding target was intended. A 2-aminopyrimidine in a hit list is a near-certain kinase hinge binder and a family-wide selectivity concern until profiled. |
| **Imidazole** | Small, flat, five-membered; one donor and one acceptor nitrogen; tautomeric; can be cationic. | Metals, especially zinc and heme iron; donor–acceptor pairs. | A metal-dependent mechanism, or an azole-type inhibition liability. Also a modelling instruction: enumerate both tautomers and both protonation states or the pose search is incomplete. |
| **Indole** | Bicyclic, flat, rigid; a large hydrophobic surface plus one NH donor at a defined edge. | Deep aromatic pockets, with the NH taking a single hydrogen bond at the rim. | Often tryptophan-mimetic or amine-neurotransmitter-related pharmacology. Its size constrains the *pocket* and not only the pose: it needs a genuinely large site, so its presence is evidence about the target. |
| **Quinoline** | Bicyclic, flat, rigid, one acceptor nitrogen; substantially more lipophilic than pyridine. | Stacking in a large aromatic slot plus one directional acceptor; metal coordination in some contexts. | A stacking or intercalating binding mode. Historically associated with antimalarial and antibacterial series, and with basic-lipophilic accumulation in acidic compartments. |
| **Piperidine** | Saturated six-membered chair with one basic nitrogen. Genuinely three-dimensional and semi-rigid: the chair is defined but substituents exchange between axial and equatorial. | The nitrogen at an acidic residue or an aromatic cage; the ring fills hydrophobic space. | The series is projecting a basic centre in a controlled direction. It also tells you the molecule has real three-dimensional shape, which matters when a pose generator is biased toward flat rings. |
| **Piperazine** | Two nitrogens across a saturated six-membered ring, acting as a rigid and roughly linear spacer with a basic centre at each end (usually one substituted). | An acidic residue at the free nitrogen; the ring itself contributes little. | Almost always a property fix rather than a binding element. A piperazine appearing late in a series usually means the team needed basicity and water solubility without disturbing the binding hypothesis. Do not assume it makes a contact. |
| **Morpholine** | Saturated six-membered ring with an ether oxygen and a weakly basic nitrogen; three-dimensional, low lipophilicity. | A weak acceptor at the oxygen, sometimes a specific and real one; otherwise solubilising bulk. | Property optimisation, with the same caution as piperazine — *except* that in a handful of target classes the morpholine oxygen is a known specific contact. Check the class before dismissing it, and say which reading you are taking. |
| **Thiophene** | Flat five-membered aromatic with sulfur; similar in size to benzene, more lipophilic and more polarisable. | Hydrophobic and aromatic contacts; the sulfur is a poor acceptor. | A bioisosteric replacement exercise. Also a metabolic flag: thiophenes can be oxidised to reactive epoxides and S-oxides, a recognised idiosyncratic-toxicity concern. |
| **Furan** | Flat five-membered aromatic with oxygen; smaller and less lipophilic than thiophene. | Weak acceptor plus hydrophobic contacts. | Usually an early hit rather than an optimised compound, because unsubstituted furans are among the more reliable structural alerts for reactive metabolite formation. |
| **Pyrazole** | Flat five-membered with two adjacent nitrogens, one donor and one acceptor; small and metabolically robust. | An adjacent donor–acceptor pair, which makes it effective at bidentate contact to a backbone edge. | A modern, property-conscious series. Pyrazole is used heavily precisely because it buys a directional two-point contact at low lipophilicity with few metabolic liabilities. Regiochemistry matters, and an NH pyrazole needs its tautomers enumerated. |
| **Steroid nucleus** | Four fused rings, essentially rigid, three-dimensional, largely hydrophobic with polar groups at defined positions on a fixed frame. | Long hydrophobic channels with polar contacts at each end; nuclear-receptor pockets in particular. | An endogenous-ligand-like mechanism and likely cross-reactivity across a receptor family. For prediction it is the easy case: the shape is non-negotiable, so there are very few conformers to consider. |
| **Macrocycle** | A large ring, typically twelve atoms or more. Far more constrained than the corresponding linear molecule, but with a genuinely populated set of accessible shapes rather than one. | Large, shallow or flat interfaces that small rigid molecules cannot cover; sometimes an internal hydrogen-bond network that shields polarity and buys permeability. | The target is probably a protein–protein interface or another site that resisted small molecules. For modelling it is the hard case: conformer enumeration is expensive and most pose-generation methods are at their worst here. |

---

## Table 3 — Target classes as compressed predictions

A class membership is not a label, it is a bundle of predictions about behaviour that
someone has already compressed. Unpacking it is the point of this section: the same
potency number means different things depending on which row the target sits in.

| Class | Pocket character | The compressed prediction |
|---|---|---|
| **Nuclear receptor** | Large, mostly buried, hydrophobic, often plastic; the functional consequence is transmitted through a distant surface. | Binding changes gene expression, so effects are indirect, delayed, and require new protein synthesis. A potency number does not translate into an effect size. |
| **Kinase** | A highly conserved nucleotide site plus adjacent variable pockets; multiple activation states. | Potency is comparatively easy and selectivity is the real problem. Measured potency depends on the assay's nucleotide concentration, and on which state you assayed. |
| **GPCR** | Ligand site at one end of a helical bundle in a membrane; several downstream coupling partners. | "Agonist" is a property of the molecule–receptor–pathway–cell system, not of the molecule. Expect biased signalling and construct-dependent structures. |
| **Protease** | An extended groove that recognises a stretched substrate rather than a compact cavity; conserved catalytic machinery. | Ligands tend to be elongated and peptide-like with poor permeability; many potent ones are covalent or transition-state mimics, so binding may be time-dependent. |
| **Cytochrome P450** | Large, flexible, mostly hydrophobic, with a heme iron; promiscuous by design. | The relationship is often dual — substrate *and* inhibitor — and inhibition may be mechanism-based. The consequence that matters is another drug's exposure, not this compound's. |
| **Transporter** | Alternating outward- and inward-facing states; the pocket differs between them. | Saturable competitive kinetics. Being transported and inhibiting transport are different behaviours needing different experiments, and tissue distribution may be dominated by this protein. |
| **Ion channel** | A gated pore with closed, open and inactivated states; drug sites are often state-specific. | Potency is under-specified without the stimulation protocol. For most programmes this class appears as a liability endpoint rather than as a target. |
| **Phosphodiesterase** | Metal-containing hydrolase with a conserved glutamine that orients the substrate and a hydrophobic clamp. | A potent ligand almost certainly engages that glutamine and stacks in the clamp — a strong, checkable pose constraint — and the downstream effect is amplified, so occupancy and effect are not proportional. |

### Unpacking each one

**Nuclear receptor.** Binding does not itself produce the effect. It changes which genes
are transcribed, which means the observable consequence needs new protein to be made, so
it appears over hours and decays over days. Two consequences follow that a potency number
alone hides. First, the same tightness of binding can produce activation, blockade, or
nothing at all, depending on which coregulator surface the bound state exposes — so
potency and efficacy dissociate, and cell type matters. Second, the right endpoint is a
transcriptional readout rather than a binding constant, and a report that quotes only the
binding constant has not measured the thing anyone cares about. For prediction, these
pockets are usually large and well represented in the structural record, but the
functionally decisive difference between two ligands may be a small shift in a helix some
distance from the ligand itself.

**Kinase.** Hundreds of family members share a highly conserved nucleotide site, so a
compound that binds one has a real prior probability of binding many. That inverts the
usual difficulty ordering: potency is the easy part and selectivity is the project. Any
hinge-binding pattern should be treated as a pan-family liability until a panel says
otherwise. The enzyme also occupies several activation states, so the conformation you
dock into determines what you find, and a compound optimised against one state may be
inactive against the physiologically relevant one. Finally, measured potency depends on
the nucleotide concentration in the assay, which means two numbers from two papers are
frequently not comparable at all.

**GPCR.** The receptor couples to more than one downstream pathway, and a compound can
activate one while leaving another untouched or suppressed. So agonism is not a property
of the molecule; it is a property of the molecule together with the receptor, the pathway
measured, and the cell it was measured in. A single "agonist" label in a database is
therefore an incomplete claim, and two sources can disagree without either being wrong.
For structure-based work, the available structures are often of a stabilised construct
captured in one state, so the pocket you dock into may not be the pocket a full agonist
requires.

**Protease.** The site is a groove built to recognise an extended substrate, not a compact
cavity built to recognise a compact molecule. Ligands therefore tend to be elongated and
peptide-like, which makes permeability and oral exposure the recurring problem rather than
potency. Because the catalytic machinery is conserved across the family, selectivity is a
family-wide problem in the same way it is for kinases. And many potent compounds are
covalent or transition-state mimics, which makes inhibition time-dependent — so an
ordinary equilibrium constant may be the wrong summary statistic, and comparing one across
two compounds with different mechanisms is meaningless.

**Cytochrome P450.** This is an enzyme whose job is to handle molecules it has never seen,
so it is promiscuous by design rather than by accident: a large, flexible, mostly
hydrophobic pocket around a heme iron. Three predictions follow. A compound is quite
likely to be both substrate and inhibitor, which are different relationships that require
different experiments. Inhibition may be mechanism-based and effectively irreversible, in
which case a simple reversible-inhibition constant misdescribes it. And the binding
geometry is set partly by *where oxidation has to happen*, not only by shape
complementarity, so a pose that is geometrically comfortable but puts no oxidisable
position near the iron is suspicious. Any ligand nitrogen able to coordinate the iron — a
pyridine, an imidazole, a triazole — is a specific, highly directional interaction worth
testing explicitly in a pose. The consequence of all this is clinical rather than
pharmacological: what matters is the effect on other drugs' exposure.

**Transporter.** A transporter moves molecules across a barrier by cycling through
conformational states, so there is no single structure and no single pocket: the
outward-facing and inward-facing states present different sites. Kinetics are saturable and
competitive, so a concentration-independent potency claim is incomplete. Crucially,
*being transported* and *inhibiting transport* are distinct behaviours that require
distinct experiments, and a compound can do one without the other. For a candidate's
behaviour in the body, this class can dominate tissue distribution — brain, liver, kidney —
over anything the molecule's passive properties would predict. For prediction, the state
you model determines the answer you get, so the state must be stated.

**Ion channel.** The relevant states are closed, open and inactivated, and drug binding is
frequently state-dependent and use-dependent. That means potency measured at one holding
potential or stimulation frequency will not equal potency at another, and a single number
is under-specified rather than merely imprecise. For most programmes this class arrives as
a liability endpoint rather than as an intended target, and the recurring offenders are
basic lipophilic amines — which is exactly why the amine rows in Table 1 carry that cost.

**Phosphodiesterase.** A metal-containing hydrolase family with two strongly conserved
recognition features: a glutamine that orients the nucleotide-like substrate through a
hydrogen-bond pair, and a hydrophobic clamp that sandwiches its ring. That gives an
unusually strong and checkable prediction — a potent ligand almost certainly engages the
glutamine and stacks in the clamp, so a pose that does neither is probably wrong. The
family's isoforms are similar enough that selectivity is a real problem with directly
clinical consequences. And the signal is amplified through a second-messenger cascade, so
fractional occupancy and fractional effect are not proportional, which again decouples a
potency number from an outcome.

---

## Turning "these two compounds share a ring system" into a checkable claim

The bare observation is a fact about chemical structure. It becomes a claim about binding
only when four things are said, in this order.

**Name the group precisely.** Not "a pyridine" but which ring, at which position in the
molecule, with which substitution pattern, and in which charge or tautomeric state you
believe it to be. Half the failures in this kind of reasoning happen here: two compounds
can contain the same ring while the neighbouring substituents leave it protonated in one
and neutral in the other, in which case they do not share the group in any sense that
matters.

**Say what it contributes.** Pick the specific capability from Table 1 rather than a
general one. "A directional hydrogen-bond acceptor at the ring nitrogen" is a claim;
"favourable interactions" is not.

**Say which pocket feature it would engage, and with what geometry.** Name the residue or
the class of residue from `stage2.critical_residues` if you have it, and name the geometry
the interaction requires — a near-linear arrangement for a halogen bond, a roughly
parallel or perpendicular ring for stacking, a donor within hydrogen-bonding distance and
in the acceptor's lone-pair direction.

**State what you would expect to observe if the claim holds, and what would falsify it.**
This is the part that converts the claim into something a stage can act on, and it is
also literally the `if_wrong` field.

Worked, on the pyridine case. The weak version is "both compounds contain a pyridine, so
they probably bind similarly". The checkable version is: *both compounds place a pyridine
nitrogen three bonds from the shared amide carbonyl. If that nitrogen is an anchor
contact, then the interaction fingerprint should show a hydrogen bond from it to the same
donor residue in both complexes; a matched pair in which the nitrogen is replaced by CH
should lose potency in both; and any pose that buries the nitrogen against a hydrophobic
wall should be rejected. If the fingerprint shows the contact in one compound and not the
other, the shared ring is a coincidence of synthesis rather than a shared binding
hypothesis, and nothing should transfer between them.*

That paragraph names the group, the contribution, the pocket feature, the expected
observation, and the falsifier. Everything an `Implication` needs is now present: the
decision is whether to treat the two compounds as one transferable case, the direction
argues for or against doing so, and `if_wrong` is the last sentence.

---

## What a shared structural motif signifies

Motif sharing is a hypothesis-generating observation. Its honest default strength in an
`Implication` is `SUGGESTIVE`, and it earns more only when an interaction fingerprint
across several complexes, or a matched-pair comparison, confirms that the shared piece is
doing the work.

**It predicts transferable behaviour when all of these hold.** The shared piece is the part
that actually contacts the protein, rather than a core that positions other things. It
carries a *directional* interaction — a hydrogen-bond pair, a metal coordination, a
halogen bond, a defined stacking geometry — rather than generic bulk, because directional
interactions are the ones whose presence or absence is detectable and whose loss is
costly. The rest of each molecule presents that piece with the same vector, so linker
length and ring substitution have not rotated it away. Both compounds fall in the same
subpopulation of size and flexibility, so the same pocket state is the relevant one. And
the contact recurs across more than one complex, which is what separates a pocket's
grammar from one ligand's idiosyncrasy.

**It does not transfer when any of these hold.** The shared piece is a property fix rather
than a binding element — a piperazine added for solubility, a morpholine added for
polarity, a benzene used as a spacer — in which case sharing it says only that two
chemists solved the same solubility problem the same way. The piece is present but
presented differently, because a changed linker or a changed substitution pattern has
moved its vector; the group is the same and the pharmacophore is not. The charge or
tautomeric state differs between the two molecules because of nearby substituents, so
they are not chemically the same group in context. Or — the case that has already cost a
real pipeline points — one compound is small enough that it does not need to engage the
anchors at all.

That last case deserves stating plainly, because it is the general form of a specific,
documented failure. In the reference PXR work
(`.claude/skills/ai-scientist/reference/pxr-case-study.md`), the crystallographic
fragments in the test set were chemically remote from every known holo ligand and often
engaged *zero* canonical pocket anchors. Any signal trained on drug-like compounds
inverted sign on them, confirmed four separate ways. The shared-motif reasoning was not
merely uninformative for those items, it was backwards. This is why anchor-based priors
are additive bonuses and never penalties for absence, why `stage1.subpopulations` exists
as a handoff key at all, and why `pocket-anatomy` is required to report per-subpopulation
validity rather than a single interaction map.

One further distinction worth keeping straight, because the same word covers both. A motif
shared between two *proteins* is a claim that two pockets present similar chemistry, which
argues about template and comparison-structure selection. A motif shared between two
*compounds* is a claim that two ligands engage a pocket similarly, which argues about
whether a binding hypothesis, a restraint, or a measured value transfers between them.
They license different implications and belong to different stages, and collapsing them is
an easy way to write a confident sentence that bears on nothing.
