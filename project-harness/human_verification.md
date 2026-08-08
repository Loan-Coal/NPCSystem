
## 2026-08-05 14:15:25 — phase gate red after EVAL-P0

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17422   2248    87%
Required test coverage of 80% reached. Total coverage: 87.10%
=========================== short test summary info ===========================
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
1 failed, 2693 passed, 29 skipped, 2232 warnings in 57.58s
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-06 13:54:07 — phase gate red after EVAL-P1

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17427   2250    87%
Required test coverage of 80% reached. Total coverage: 87.09%
=========================== short test summary info ===========================
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
1 failed, 2721 passed, 29 skipped, 2232 warnings in 67.86s (0:01:07)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-06 14:14:57 — task EVAL-P2.1 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-06 14:25:04 — task EVAL-P2.2 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-06 23:02:38 — task EVAL-P3.1 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-06 23:20:54 — task EVAL-P3.3 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-07 00:52:15 — phase gate red after EVAL-P4

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17429   2250    87%
Required test coverage of 80% reached. Total coverage: 87.09%
=========================== short test summary info ===========================
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
1 failed, 2799 passed, 29 skipped, 2232 warnings in 64.20s (0:01:04)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-07 01:15:30 — task EVAL-P5.1 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-07 01:23:31 — task EVAL-P5.3 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-07 01:39:41 — phase gate red after EVAL-P5

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17429   2250    87%
Required test coverage of 80% reached. Total coverage: 87.09%
=========================== short test summary info ===========================
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
1 failed, 2827 passed, 29 skipped, 2232 warnings in 65.86s (0:01:05)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-07 17:31:45 — phase gate red after EVAL-P1

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17433   2251    87%
Required test coverage of 80% reached. Total coverage: 87.09%
=========================== short test summary info ===========================
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
1 failed, 2844 passed, 29 skipped, 2232 warnings in 70.56s (0:01:10)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-07 17:43:23 — no status token from task EVAL-P5.5

The session ended without a bare AUTO_STATUS line. Log: C:/Users/lohan/Documents/hackathons/NPCSystem/project-harness/.loop-logs/task-EVAL-P5.5-1786117385.log

## 2026-08-08 11:14:20 — task EVAL-P9.1 introduced a confirmed regression

Committed anyway as visible debt (scar 6.5). Run 1 of 3.

## 2026-08-08 11:28:53 — task EVAL-P9.2 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-08 11:50:28 — task EVAL-P9.4 introduced a confirmed regression

Committed anyway as visible debt (scar 6.5). Run 1 of 3.

## 2026-08-08 11:53:42 — phase gate red after EVAL-P9

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case

src\npc_engine\services\content_rating_resolver.py                               7      0   100%
src\npc_engine\services\input_moderation.py                                     21      0   100%
src\npc_engine\services\output_moderation.py                                    16      0   100%
src\npc_engine\setup\__init__.py                                                 1      0   100%
src\npc_engine\setup\first_run_flow.py                                          56      7    88%   101, 125-126, 135-136, 156-157
src\npc_engine\setup\model_tiers.py                                             13      0   100%
src\npc_engine\setup\neo4j_manager.py                                           30      0   100%
src\npc_engine\setup\ollama_manager.py                                          59     16    73%   120, 147-156, 169-179
src\npc_engine\setup\path_validator.py                                          81      3    96%   126, 140-141
src\npc_engine\setup\stack_launcher.py                                          89     16    82%   91-92, 162, 185-190, 198-203, 233
src\npc_engine\setup\vram_detector.py                                           19      0   100%
src\npc_engine\setup\wizard_config.py                                           31      0   100%
src\npc_engine\type_registry\__init__.py                                         5      0   100%
src\npc_engine\type_registry\base_contract_loader.py                            62     10    84%   43, 57, 73-74, 82-83, 89-92
src\npc_engine\type_registry\base_contract_models.py                            30      0   100%
src\npc_engine\type_registry\contracts.py                                       43      0   100%
src\npc_engine\type_registry\extension_loader.py                                56      9    84%   55, 68-71, 75, 86, 92-93
src\npc_engine\type_registry\field_validators.py                                60      6    90%   104, 110, 123, 129, 135, 140
src\npc_engine\type_registry\merge_field_builders.py                            37      4    89%   39-45, 86
src\npc_engine\type_registry\merge_rules.py                                     59     12    80%   105-109, 117-126, 143-144, 152-158
src\npc_engine\type_registry\node_validator.py                                   8      1    88%   36
src\npc_engine\type_registry\registry.py                                        14      0   100%
src\npc_engine\type_registry\runtime_models.py                                  83      2    98%   87, 138
src\npc_engine\type_registry\serializer.py                                      34      4    88%   48-50, 61
src\npc_engine\type_registry\validation.py                                      84     12    86%   51, 91, 95, 141-143, 153-157, 169-170
src\npc_engine\utils\__init__.py                                                 1      0   100%
src\npc_engine\utils\errors.py                                                 157      2    99%   316, 337
src\npc_engine\utils\logging.py                                                 32      0   100%
src\npc_engine\utils\metrics.py                                                 82      1    99%   45
src\npc_engine\world\__init__.py                                                 1      0   100%
src\npc_engine\world\time_utils.py                                              29      0   100%
src\npc_engine\world\world_state.py                                             18      0   100%
src\npc_engine\world\world_time_service.py                                      38      0   100%
----------------------------------------------------------------------------------------------------------
TOTAL                                                                        17466   2248    87%
Required test coverage of 80% reached. Total coverage: 87.13%
=========================== short test summary info ===========================
FAILED tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
1 failed, 2921 passed, 29 skipped, 2265 warnings in 85.24s (0:01:25)
make: *** [Makefile:50: test-cov] Error 1
