"""Tests du registre, centrés sur la normalisation et le scoring : c'est le
cœur métier du rapprochement et le sujet le plus probable en entretien
(voir CLAUDE.md, section « Tests »)."""

from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from .models import Commune, Menage, PaireSuspecte
from .services.rapprochement import (
    SEUIL_SCORE,
    calculer_score,
    normaliser_nom,
    rapprocher_menages,
    renseigner_champs_derives,
)


class NormalisationTests(SimpleTestCase):
    """Tests purs sur les chaînes : pas de base de données nécessaire."""

    def test_consonnes_geminees_abdoullaye_abdoulaye(self):
        self.assertEqual(normaliser_nom("Abdoullaye"), normaliser_nom("Abdoulaye"))

    def test_racine_onomastique_mahamadou_mohamed(self):
        self.assertEqual(normaliser_nom("Mahamadou"), normaliser_nom("Mohamed"))

    def test_particule_ag_mohamed(self):
        self.assertEqual(normaliser_nom("Ag Mohamed"), normaliser_nom("Mohamed"))

    def test_nom_vide(self):
        self.assertEqual(normaliser_nom(""), "")


class RapprochementTests(TestCase):
    """Tests de scoring et de blocage, avec de vrais Menage en base."""

    @classmethod
    def setUpTestData(cls):
        cls.commune_a = Commune.objects.create(
            code="NE001_01_01", nom="Agadez", departement="NE001_01", region="Agadez"
        )
        cls.commune_b = Commune.objects.create(
            code="NE002_01_01", nom="Diffa", departement="NE002_01", region="Diffa"
        )

    def _creer_menage(self, **kwargs):
        defaults = {
            "submission_id": uuid4().hex,
            "commune": self.commune_a,
            "sexe": "M",
        }
        defaults.update(kwargs)
        menage = Menage(**defaults)
        renseigner_champs_derives(menage)
        menage.save()
        return menage

    def test_freres_meme_village_restent_sous_le_seuil(self):
        frere_1 = self._creer_menage(nom_chef="Issoufou", prenom_chef="Moussa", age=45, village="Tanout")
        frere_2 = self._creer_menage(nom_chef="Issoufou", prenom_chef="Abdou", age=30, village="Tanout")

        score, _ = calculer_score(frere_1, frere_2)

        self.assertLess(score, SEUIL_SCORE)

    def test_coepouses_remontent_au_dessus_du_seuil(self):
        epouse_1 = self._creer_menage(
            nom_chef="Garba", prenom_chef="Fati", sexe="F", age=28, village="Tanout",
            telephone="90112233", latitude="17.000000", longitude="8.000000",
        )
        epouse_2 = self._creer_menage(
            nom_chef="Garba", prenom_chef="Halima", sexe="F", age=25, village="Tanout",
            telephone="90112233", latitude="17.000010", longitude="8.000010",
        )

        score, motifs = calculer_score(epouse_1, epouse_2)

        self.assertGreaterEqual(score, SEUIL_SCORE)
        self.assertTrue(any("téléphone" in motif for motif in motifs))

    def test_sexe_different_penalise_le_score(self):
        menage_1 = self._creer_menage(nom_chef="Hama", prenom_chef="Issa", sexe="M")
        menage_2 = self._creer_menage(nom_chef="Hama", prenom_chef="Issa", sexe="F")

        score, motifs = calculer_score(menage_1, menage_2)

        self.assertTrue(any("sexe différent" in motif for motif in motifs))

    def test_homonyme_autre_region_non_compare_faute_de_bloc_commun(self):
        self._creer_menage(nom_chef="Moussa", prenom_chef="Ibrahim", commune=self.commune_a)
        self._creer_menage(nom_chef="Moussa", prenom_chef="Ibrahim", commune=self.commune_b)

        nb_paires = rapprocher_menages()

        self.assertEqual(nb_paires, 0)
        self.assertEqual(PaireSuspecte.objects.count(), 0)

    def test_rapprocher_menages_cree_une_paire_au_dessus_du_seuil(self):
        self._creer_menage(
            nom_chef="Garba", prenom_chef="Fati", sexe="F", age=28, village="Tanout",
            telephone="90112233", latitude="17.000000", longitude="8.000000",
        )
        self._creer_menage(
            nom_chef="Garba", prenom_chef="Halima", sexe="F", age=25, village="Tanout",
            telephone="90112233", latitude="17.000010", longitude="8.000010",
        )

        nb_paires = rapprocher_menages()

        self.assertEqual(nb_paires, 1)
        paire = PaireSuspecte.objects.get()
        self.assertEqual(paire.statut, PaireSuspecte.Statut.EN_ATTENTE)
        self.assertLess(paire.menage_a_id, paire.menage_b_id)

    def test_rapprocher_menages_est_idempotent(self):
        self._creer_menage(
            nom_chef="Garba", prenom_chef="Fati", sexe="F",
            telephone="90112233", village="Tanout",
        )
        self._creer_menage(
            nom_chef="Garba", prenom_chef="Halima", sexe="F",
            telephone="90112233", village="Tanout",
        )

        rapprocher_menages()
        nb_nouvelles_paires = rapprocher_menages()

        self.assertEqual(nb_nouvelles_paires, 0)
        self.assertEqual(PaireSuspecte.objects.count(), 1)
