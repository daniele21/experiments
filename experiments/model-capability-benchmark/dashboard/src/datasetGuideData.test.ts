import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  activeDatasetGuides,
  datasetGuides,
  difficultyTotal,
  getDatasetGuide,
  getDatasetVersions,
  historicalDatasetGuides,
} from './datasetGuideData.ts';

describe('Dataset guide and historical continuity', () => {
  it('has an unambiguous record for each registered benchmark dataset', () => {
    assert.equal(datasetGuides.length, 9);
    assert.equal(new Set(datasetGuides.map(guide => guide.id)).size, datasetGuides.length);
    assert.equal(activeDatasetGuides.length, 5);
    assert.equal(historicalDatasetGuides.length, 4);
    for (const guide of datasetGuides) {
      assert.ok(guide.purpose && guide.measures && guide.metric && guide.example.input && guide.example.output);
      assert.ok(guide.capabilityIds.length >= 1);
      assert.equal(getDatasetGuide(guide.id), guide);
      if (guide.caseCount !== null && guide.families) {
        assert.equal(guide.families.reduce((count, item) => count + item.count, 0), guide.caseCount);
      }
      if (guide.difficulty) {
        assert.equal(difficultyTotal(guide), guide.caseCount);
      }
      if (guide.tiers && guide.caseCount !== null) {
        assert.ok(guide.tiers.smoke <= guide.tiers.core);
        assert.ok(guide.tiers.core <= guide.tiers.extended);
        assert.ok(guide.tiers.extended <= guide.caseCount);
      }
    }
  });

  it('keeps all three mathematical versions and clearly marks v3 as active', () => {
    const versions = getDatasetVersions('Math reasoning');
    assert.deepEqual(versions.map(guide => guide.version), [1, 2, 3]);
    assert.deepEqual(versions.map(guide => guide.caseCount), [10, 40, 72]);
    assert.deepEqual(versions.map(guide => guide.status), ['historical', 'historical', 'current']);
    assert.deepEqual(versions[2].tiers, { smoke: 12, core: 40, extended: 72 });
    assert.equal(versions[2].difficulty?.challenge, 16);
  });

  it('handles future unregistered datasets without inventing metadata', () => {
    assert.equal(getDatasetGuide('future-custom-dataset'), undefined);
    assert.deepEqual(getDatasetVersions('non-existent'), []);
  });
});
