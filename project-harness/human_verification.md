
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

## 2026-08-08 12:18:40 — task EVAL-P10.1 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-08 12:27:54 — task EVAL-P10.2 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-08 12:48:37 — phase gate red after EVAL-P10

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
TOTAL                                                                        17477   2249    87%
Required test coverage of 80% reached. Total coverage: 87.13%
=========================== short test summary info ===========================
FAILED tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
1 failed, 2931 passed, 29 skipped, 2265 warnings in 92.88s (0:01:32)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-09 23:17:43 — phase gate red after EVAL-P11

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

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
TOTAL                                                                        17477   2248    87%
Required test coverage of 80% reached. Total coverage: 87.14%
=========================== short test summary info ===========================
FAILED tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue
3 failed, 2978 passed, 29 skipped, 2265 warnings in 81.14s (0:01:21)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-09 23:45:12 — task EVAL-P12.2 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-09 23:59:18 — phase gate red after EVAL-P12

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire

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
TOTAL                                                                        17477   2248    87%
Required test coverage of 80% reached. Total coverage: 87.14%
=========================== short test summary info ===========================
FAILED tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
FAILED tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue
3 failed, 3002 passed, 29 skipped, 2265 warnings in 84.71s (0:01:24)
make: *** [Makefile:50: test-cov] Error 1

## 2026-08-10 16:52:28 — no status token from task EVAL-P15.2

The session ended without a bare AUTO_STATUS line. Log: C:/Users/lohan/Documents/hackathons/NPCSystem/project-harness/.loop-logs/task-EVAL-P15.2-1786373346.log

## 2026-08-10 23:12:21 — no status token from task EVAL-P15.5

The session ended without a bare AUTO_STATUS line. Log: C:/Users/lohan/Documents/hackathons/NPCSystem/project-harness/.loop-logs/task-EVAL-P15.5-1786396035.log

## 2026-08-11 17:08:04 — no status token from task EVAL-P15.6

The session ended without a bare AUTO_STATUS line. Log: C:/Users/lohan/Documents/hackathons/NPCSystem/project-harness/.loop-logs/task-EVAL-P15.6-1786436860.log

## 2026-08-12 02:44:07 — phase gate red after EVAL-P17

CLASSIFICATION=UNATTRIBUTED FAILED_CHECK=coverage-or-unknown

    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\evals\test_sequence_records.py::test_turn_is_frozen:152  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\evals\test_sequence_records.py::test_reset_receipt_is_frozen:158  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\evals\test_sequence_runner.py::test_sequence_result_is_immutable:164  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\graph\test_quest_phase4.py::test_frozen:97  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\graph\test_transfer_validators.py::test_currency_command_is_frozen:71  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\graph\test_transfer_validators.py::test_item_command_is_frozen:168  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\llm\test_llm_config.py::test_relevance_weights_is_frozen:67  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\llm\test_llm_config.py::test_llm_config_rejects_extra_fields:84  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\llm\test_tts_voice_params.py::test_voice_params_is_frozen:41  pytest.raises(Exception) — use a specific exception type
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\retrieval\test_context_scoring.py::test_relevance_weights_explicit_causes_sum_to_exceed_one:389  pytest.raises(Exception) — use a specific exception type

  SELF_REFERENTIAL_SUM (1):
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\evals\test_retrieval_join.py::test_four_cells_sum_to_annotated_count:150  sum-of-parts == total where total is derived from the same parts

  VACUOUS_MOCK_NOT_CALLED (8):
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\config\test_seed_chain_quests.py::test_seed_chain_quests_non_fatal_on_exception:78  assert mock_edge.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\config\test_seed_chain_quests.py::test_seed_source_chain_quests_non_fatal_on_exception:136  assert mock_edge.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\engines\test_intent_queue_writer.py::test_enqueue_drops_new_when_at_cap_and_new_score_lower:115  assert mock_delete.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\engines\test_intent_queue_writer.py::test_enqueue_drops_new_when_at_cap_and_new_score_lower:116  assert mock_merge.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\evals\test_deterministic_pass.py::test_scores_every_record_without_llm:89  assert mock_judge.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\graph\test_event_reputation_wiring.py::test_emit_skips_reputation_when_no_faction:130  assert mock_rep.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\graph\test_gossip_repository.py::test_log_gossip_skips_missing_edge:261  assert mock_update.call_count == 0 — verify the patched symbol is reachable by the SUT
    C:\Users\lohan\Documents\hackathons\NPCSystem\tests\unit\test_judge_runner.py::test_judge_kind_none_is_skipped:163  assert mock_judge.call_count == 0 — verify the patched symbol is reachable by the SUT

Each item must be fixed or suppressed with '# quality-ok: <reason>'.
.venv/Scripts/python.exe scripts/check_conservation.py
Conservation audit: C:\Users\lohan\Documents\hackathons\NPCSystem\evals\generations\k3_73e6c36

  Identity 1 [FAIL]: guard_cases + capability_cases == total_cases
    78 guard + 7 capability = 85 of 94 cases; 9 cases in no battery
  Identity 2 [FAIL]: slots_read_by_compare == |judged ∪ deterministic_judged|
    compare reads 115 of 307 unique record_ids (345 of 921 rows with repetitions) — 62.5% never read
  Identity 3 [FAIL]: capability_battery_cases == capability_cases_actually_run
    capability battery sees 2, while 7 capability cases ran

  Identity 4 [DEFERRED to EVAL-P17.4]: sum(battery case counts) == unique cases in outputs
    Deferred: right-hand side measures a different population from a live eval run.

3 violation(s) found.
make: *** [Makefile:165: check-conservation] Error 3

## 2026-08-15 09:20:17 — task EVAL-P13.2 committed with a pre-existing red gate

Every failure pre-dated this task (baseline attribution). Nothing new broke.

## 2026-08-15 09:25:58 — phase gate red after EVAL-P13

CLASSIFICATION=HALT FAILED_CHECK=tests
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire
FAILING tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_parses_and_verifies_clean

.venv/Scripts/python.exe -m ruff check src/ evals/
E741 Ambiguous variable name: `l`
  --> evals\sequence_order_effect.py:81:46
   |
79 |         return None  # every scenario is uniformly all-pass or all-fail: Q is undefined
80 |
81 |     numerator = (k - 1) * (k * sum(l * l for l in col_sums) - sum(col_sums) ** 2)
   |                                              ^
82 |     q = numerator / denominator
83 |     p = chi2_sf(q, df=k - 1)
   |

Found 1 error.
make: *** [Makefile:99: lint] Error 1
